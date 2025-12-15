class ExponentialMovingAverage:
    """
    Exponential Moving Average (EMA) untuk smoothing sinyal EAR/MAR
    pada sistem deteksi kantuk berbasis visi komputer.

    Author  : Farrel Zandra
    NIM     : 231524007

    Attributes:
        alpha (float): smoothing factor (0 < alpha <= 1)
        value (float | None): nilai EMA sebelumnya
    """

    def __init__(self, alpha: float = 0.3):
        if not 0 < alpha <= 1:
            raise ValueError("Alpha harus berada pada rentang (0, 1].")

        self.alpha = alpha
        self.value = None

    def update(self, current_value: float) -> float:
        """
        Update nilai EMA berdasarkan input terbaru.

        Args:
            current_value (float): nilai EAR atau MAR terbaru

        Returns:
            float: nilai EMA yang telah dismoothing
        """
        if self.value is None:
            # Inisialisasi EMA dengan nilai pertama
            self.value = current_value
        else:
            self.value = (
                self.alpha * current_value
                + (1 - self.alpha) * self.value
            )

        return self.value

    def reset(self):
        """
        Reset nilai EMA (misalnya saat user berganti atau wajah tidak terdeteksi).
        """
        self.value = None
