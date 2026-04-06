import numpy as np
from collections import deque

SAMPLE_RATE = 16000


def compute_dbfs(audio_block: np.ndarray) -> float:
    samples = audio_block.astype(np.float64, copy=False)
    rms = np.sqrt(np.mean(samples * samples))
    return 20.0 * np.log10(max(rms, 1.0e-12))


class EnergyVoiceGate:
    def __init__(
        self,
        *,
        threshold_db: float = -40.0,
        silence_seconds: float = 0.8,
        sample_rate: int = SAMPLE_RATE,
        preroll_blocks: int = 2,
    ):
        self.threshold_db = threshold_db
        self.silence_seconds = silence_seconds
        self.sample_rate = sample_rate
        self.preroll_blocks = preroll_blocks
        self.reset()

    @property
    def silence_samples_target(self) -> int:
        return int(self.silence_seconds * self.sample_rate)

    def process(self, audio_block: np.ndarray) -> tuple[list[np.ndarray], bool]:
        is_speech = compute_dbfs(audio_block) > self.threshold_db
        emitted_blocks: list[np.ndarray] = []
        should_finalize = False

        if self.in_speech:
            emitted_blocks.append(audio_block)
            if is_speech:
                self.silence_samples = 0
            else:
                self.silence_samples += len(audio_block)
                should_finalize = self.silence_samples >= self.silence_samples_target
                if should_finalize:
                    self.pre_roll.clear()
        else:
            self.pre_roll.append(audio_block.copy())
            if is_speech:
                self.in_speech = True
                self.silence_samples = 0
                emitted_blocks = list(self.pre_roll)
                self.pre_roll.clear()

        return emitted_blocks, should_finalize

    def reset(self) -> None:
        self.in_speech = False
        self.silence_samples = 0
        self.pre_roll = deque(maxlen=max(1, self.preroll_blocks))
