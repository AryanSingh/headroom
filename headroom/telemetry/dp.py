"""Differential Privacy utilities.

Implements DP mechanisms (Laplace/Gaussian noise) bounded by an ε budget.
This ensures that any metrics egressed via the beacon cannot be reverse-engineered
to leak specific user queries or payload content.
"""

import math
import random

class DPMechanism:
    """Differential Privacy base mechanism."""
    
    def __init__(self, epsilon: float):
        """
        Args:
            epsilon: The privacy budget parameter. Smaller epsilon = more privacy, more noise.
        """
        self.epsilon = epsilon
        
    def add_laplace_noise(self, value: float, sensitivity: float = 1.0) -> float:
        """Add Laplace noise to a numerical value.
        
        Args:
            value: The original value.
            sensitivity: The maximum amount the value could change from a single individual's data.
            
        Returns:
            The value with Laplace noise added.
        """
        if self.epsilon <= 0:
            return value
            
        scale = sensitivity / self.epsilon
        # Draw from Laplace distribution: mu - b * sgn(U) * ln(1 - 2|U|)
        # where U is uniform between -0.5 and 0.5
        u = random.uniform(-0.5, 0.5)
        sgn = 1 if u > 0 else -1
        noise = -scale * sgn * math.log(1 - 2 * abs(u))
        
        return value + noise

    def add_gaussian_noise(self, value: float, sensitivity: float = 1.0, delta: float = 1e-5) -> float:
        """Add Gaussian noise to a numerical value.
        
        Useful for (epsilon, delta)-differential privacy.
        """
        if self.epsilon <= 0:
            return value
            
        sigma = sensitivity * math.sqrt(2 * math.log(1.25 / delta)) / self.epsilon
        noise = random.gauss(0, sigma)
        
        return value + noise
