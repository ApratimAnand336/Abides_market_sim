import numpy as np

class OrderSizeModel:
    def __init__(self) -> None:
        # Pomegranate mixture model equivalent:
        self.weights = [
            0.2, 0.7, 0.06, 0.004, 0.0329, 0.001, 0.0006, 0.0004, 0.0005, 0.0003, 0.0003
        ]
        # Normalize weights to sum exactly to 1 for numpy
        self.weights = np.array(self.weights) / sum(self.weights)
        
        self.dists = [
            ("lognormal", 2.9, 1.2),
            ("normal", 100.0, 0.15),
            ("normal", 200.0, 0.15),
            ("normal", 300.0, 0.15),
            ("normal", 400.0, 0.15),
            ("normal", 500.0, 0.15),
            ("normal", 600.0, 0.15),
            ("normal", 700.0, 0.15),
            ("normal", 800.0, 0.15),
            ("normal", 900.0, 0.15),
            ("normal", 1000.0, 0.15),
        ]

    def sample(self, random_state: np.random.RandomState) -> float:
        idx = random_state.choice(len(self.weights), p=self.weights)
        dist_type, p1, p2 = self.dists[idx]
        
        if dist_type == "lognormal":
            # The parameters 2.9, 1.2 correspond to mu, sigma in the underlying normal dist
            val = random_state.lognormal(mean=p1, sigma=p2)
        else:
            val = random_state.normal(loc=p1, scale=p2)
            
        return max(1, round(val))
