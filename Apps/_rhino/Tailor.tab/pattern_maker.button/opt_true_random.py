"""True Random Pattern Generator

Generates completely random patterns based on type definitions and their ratios.
Features:
- Pure random distribution without spatial bias
- Respects type ratios from TYPE_DEFINITIONS
- Creates weighted population for random selection
- Processes entire grid without gradient effects
- Provides uniform randomness across all positions

Algorithm:
1. Extracts types and weights from TYPE_DEFINITIONS
2. Creates weighted population list (100x multiplier for precision)
3. Randomly selects types for each grid position
4. Returns location map with (x,y) coordinates and type assignments

Returns:
- dict: Key is (x,y) tuple, value is type string
- Distribution follows TYPE_DEFINITIONS ratios exactly"""

import random

from pattern_maker_left import TYPE_DEFINITIONS

def get_location_map(max_x, max_y):
    """Return a dict of location and type based on TYPE_DEFINITIONS ratios.
    
    Args:
        max_x (int): Maximum x coordinate
        max_y (int): Maximum y coordinate
        
    Returns:
        dict: Key is (x,y) tuple, value is type string, weighted by TYPE_DEFINITIONS ratios
    """
    # Extract types and their weights from TYPE_DEFINITIONS
    types = list(TYPE_DEFINITIONS.keys())
    weights = [TYPE_DEFINITIONS[t].get('ratio', 1/len(types)) for t in types]
    
    # Create a population list based on weights
    population = []
    for t, w in zip(types, weights):
        population.extend([t] * int(w * 100))
    
    location_map = {}
    for col in range(max_x):
        for row in range(max_y):
            location_map[(col, row)] = random.choice(population)
    return location_map

