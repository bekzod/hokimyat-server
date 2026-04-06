import tarfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import onnxruntime as ort
import sentencepiece as spm
import torch
import yaml
from huggingface_hub import hf_hub_download
from nemo.collections.asr.modules import AudioToMelSpectrogramPreprocessor

SAMPLE_RATE = 16000


@dataclass
class StreamingConfig:
    feature_cache_frames: int
    channel_cache_shape: tuple[int, int, int, int]
    time_cache_shape: tuple[int, int, int, int]


def resolve_nemo_archive(model_name: str, nemo_filename: str) -> Path:
    model_path = Path(model_name)
    if model_path.suffix == ".nemo" and model_path.exists():
        return model_path
    return Path(hf_hub_download(repo_id=model_name, filename=nemo_filename))


def read_tar_member(archive: tarfile.TarFile, filename: str) -> bytes:
    for member in archive.getmembers():
        if Path(member.name).name != filename:
            continue
        extracted = archive.extractfile(member)
        if extracted is None:
            break
        return extracted.read()
    raise FileNotFoundError(f"Could not find {filename} inside {archive.name}")


def load_nemo_metadata(
    model_name: str,
    nemo_filename: str,
) -> tuple[dict, spm.SentencePieceProcessor]:
    nemo_archive = resolve_nemo_archive(model_name, nemo_filename)
    with tarfile.open(nemo_archive, "r:*") as archive:
        model_config = yaml.safe_load(read_tar_member(archive, "model_config.yaml"))
        tokenizer_filename = Path(
            model_config["tokenizer"]["model_path"].split("nemo:", 1)[-1]
        ).name
        tokenizer_bytes = read_tar_member(archive, tokenizer_filename)

    tokenizer = spm.SentencePieceProcessor()
    tokenizer.LoadFromSerializedProto(tokenizer_bytes)
    return model_config, tokenizer


def build_preprocessor(model_config: dict) -> AudioToMelSpectrogramPreprocessor:
    preprocessor_config = {
        key: value
        for key, value in model_config["preprocessor"].items()
        if not key.startswith("_")
    }
    preprocessor = AudioToMelSpectrogramPreprocessor(**preprocessor_config)
    preprocessor.eval()
    return preprocessor


def build_streaming_config(model_config: dict) -> StreamingConfig:
    encoder_config = model_config["encoder"]
    conv_context_size = encoder_config.get("conv_context_size")
    if conv_context_size == "causal":
        conv_context_size = [encoder_config["conv_kernel_size"] - 1, 0]
    elif conv_context_size is None:
        kernel_size = encoder_config["conv_kernel_size"]
        conv_context_size = [(kernel_size - 1) // 2, (kernel_size - 1) // 2]

    return StreamingConfig(
        feature_cache_frames=encoder_config["subsampling_factor"] + 1,
        channel_cache_shape=(
            1,
            encoder_config["n_layers"],
            encoder_config["att_context_size"][0],
            encoder_config["d_model"],
        ),
        time_cache_shape=(
            1,
            encoder_config["n_layers"],
            encoder_config["d_model"],
            conv_context_size[0],
        ),
    )


def zero_state_from_shape(shape) -> np.ndarray:
    resolved_shape = [1 if isinstance(dim, str) else dim for dim in shape]
    return np.zeros(resolved_shape, dtype=np.float32)


class RNNTModelBundle:
    """Shared ONNX RNNT model resources — loaded once, used by all streaming sessions."""

    def __init__(
        self,
        *,
        encoder_onnx_path: str,
        decoder_joint_onnx_path: str,
        model_name: str,
        nemo_filename: str,
        providers: list[str] | None = None,
        max_symbols_per_step: int = 10,
    ):
        if providers is None:
            providers = ["CPUExecutionProvider"]

        model_config, self.tokenizer = load_nemo_metadata(model_name, nemo_filename)
        self.preprocessor = build_preprocessor(model_config)
        self.streaming_config = build_streaming_config(model_config)
        self.blank_id = model_config["decoder"]["vocab_size"]
        self.max_symbols_per_step = max_symbols_per_step
        self.n_features = model_config["preprocessor"]["features"]

        self.encoder = ort.InferenceSession(encoder_onnx_path, providers=providers)
        self.decoder_joint = ort.InferenceSession(
            decoder_joint_onnx_path, providers=providers
        )

        self.encoder_input_names = {item.name for item in self.encoder.get_inputs()}
        self.encoder_output_names = [item.name for item in self.encoder.get_outputs()]
        self.decoder_input_names = [
            item.name for item in self.decoder_joint.get_inputs()
        ]
        self.decoder_output_names = [
            item.name for item in self.decoder_joint.get_outputs()
        ]
        self.state_input_names = sorted(
            name
            for name in self.decoder_input_names
            if name.startswith("input_states_")
        )
        self.state_output_names = sorted(
            name
            for name in self.decoder_output_names
            if name.startswith("output_states_")
        )
        self.predictor_state_templates = [
            zero_state_from_shape(item.shape)
            for item in self.decoder_joint.get_inputs()
            if item.name in self.state_input_names
        ]


class StreamingRecognizerState:
    """Per-session mutable state for streaming RNNT recognition.

    Each WebSocket connection creates its own instance while sharing the
    underlying RNNTModelBundle (ONNX sessions are thread-safe for inference).
    """

    def __init__(self, model: RNNTModelBundle):
        self.model = model
        self.feature_cache = np.zeros(
            (model.n_features, model.streaming_config.feature_cache_frames),
            dtype=np.float32,
        )
        self.channel_cache = np.zeros(
            model.streaming_config.channel_cache_shape, dtype=np.float32
        )
        self.time_cache = np.zeros(
            model.streaming_config.time_cache_shape, dtype=np.float32
        )
        self.cache_lengths = np.zeros((1,), dtype=np.int64)
        self.predictor_states = [s.copy() for s in model.predictor_state_templates]
        self.last_token = model.blank_id
        self.tokens: list[int] = []

    def reset(self) -> None:
        self.feature_cache.fill(0.0)
        self.channel_cache.fill(0.0)
        self.time_cache.fill(0.0)
        self.cache_lengths.fill(0)
        self.predictor_states = [s.copy() for s in self.model.predictor_state_templates]
        self.last_token = self.model.blank_id
        self.tokens.clear()

    def current_text(self) -> str:
        return self.model.tokenizer.decode(self.tokens).strip()

    def transcribe_chunk(self, chunk: np.ndarray) -> str:
        model = self.model
        with torch.no_grad():
            audio_tensor = torch.from_numpy(chunk).unsqueeze(0)
            audio_lengths = torch.tensor([chunk.shape[0]], dtype=torch.int64)
            features, feature_lengths = model.preprocessor(
                input_signal=audio_tensor,
                length=audio_lengths,
            )

        feature_length = int(feature_lengths[0].item())
        if feature_length == 0:
            return self.current_text()

        features_np = features[0, :, :feature_length].cpu().numpy().astype(np.float32)
        features_with_cache = np.concatenate(
            [self.feature_cache, features_np], axis=1
        )
        encoder_inputs = {
            "audio_signal": features_with_cache[np.newaxis, :, :],
            "length": np.array([features_with_cache.shape[1]], dtype=np.int64),
            "cache_last_channel": self.channel_cache,
            "cache_last_time": self.time_cache,
            "cache_last_channel_len": self.cache_lengths,
        }
        self.feature_cache = features_with_cache[
            :, -model.streaming_config.feature_cache_frames :
        ]

        encoder_outputs = dict(
            zip(
                model.encoder_output_names,
                model.encoder.run(None, encoder_inputs),
            )
        )
        self.channel_cache = encoder_outputs["cache_last_channel_next"].astype(
            np.float32
        )
        self.time_cache = encoder_outputs["cache_last_time_next"].astype(np.float32)
        self.cache_lengths = encoder_outputs["cache_last_channel_next_len"].astype(
            np.int64
        )

        encoded = encoder_outputs["outputs"].astype(np.float32)
        encoded_length = int(encoder_outputs["encoded_lengths"][0])
        if encoded_length <= 0:
            return self.current_text()

        self._decode_encoder_outputs(encoded[:, :, :encoded_length], encoded_length)
        return self.current_text()

    def _decode_encoder_outputs(
        self, encoder_outputs: np.ndarray, encoded_length: int
    ) -> None:
        model = self.model
        for time_idx in range(encoded_length):
            frame = encoder_outputs[:, :, time_idx : time_idx + 1]
            symbols_added = 0

            while (
                model.max_symbols_per_step is None
                or symbols_added < model.max_symbols_per_step
            ):
                decoder_inputs = {
                    "encoder_outputs": frame,
                    "targets": np.array([[self.last_token]], dtype=np.int32),
                    "target_length": np.array([1], dtype=np.int32),
                }
                for name, state in zip(
                    model.state_input_names, self.predictor_states
                ):
                    decoder_inputs[name] = state

                decoder_outputs = dict(
                    zip(
                        model.decoder_output_names,
                        model.decoder_joint.run(None, decoder_inputs),
                    )
                )
                logits = decoder_outputs["outputs"][0, 0, 0, :]
                token_id = int(np.argmax(logits))

                if token_id == model.blank_id:
                    break

                self.predictor_states = [
                    decoder_outputs[name].astype(np.float32)
                    for name in model.state_output_names
                ]
                self.last_token = token_id
                self.tokens.append(token_id)
                symbols_added += 1
