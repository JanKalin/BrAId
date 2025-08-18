import numpy as np

def distances_and_groups(pulses, scale, group_max_distance=1.8):
    """
    Returns axle distances and groups

    Parameters
    ----------
    pulses : list(int)
        A list of axle pulses.
    scale : float
        scaling factor between pulses and axle distances.
    group_max_distance : float, optional
        Axles closer than this value are considered a part of a group.
        The default is 1.8.

    Returns
    -------
    A tuple, where the first element is a list of axle distances and the second
    element is a string containing axle groups.

    """
    
    # Axle distances are simple
    axle_distances = [(y - x)/scale for (x, y) in zip(pulses[:-1], pulses[1:])]
    
    # Join into groups
    axle_groups = ""
    size = 1
    for a in axle_distances:
        if a > group_max_distance:
            axle_groups += str(size)
            size = 1
        else:
            size += 1
    axle_groups += str(size)
    
    # Done
    return (axle_distances, axle_groups)

def fuzzy_match(a, b, tol=0.25, precision=6):
    """
    Returns true if the arrays a1 and a2 are the same length and the elements
    are within `tolerance` of each other.

    Parameters
    ----------
    a : list(float)
        First array.
    b : list(float)
        Second array.
    tol : float, optional
        Tolerance for match. The default is 0.25.
    precision : int, optional
        Precision for comparison. Values from NSWD are only precise to 6
        significant figures.

    Returns
    -------
    bool.

    """
    
    if len(a) != len(b):
        return False
    a = np.array([float(f"{x:.{precision}g}") for x in a])
    b = np.array([float(f"{x:.{precision}g}") for x in b])
    return (np.abs(a - b) <= tol).all()

# Test
pulses = [516, 591, 717, 744, 772]
scale = 21.134021895176904
true_axle_distances = [3.54878, 5.96195, 1.27756, 1.32488]
true_groups = "113"
tolerance = 0.25

(axle_distances, axle_groups) = distances_and_groups(pulses, scale)
print("Distances match:",
      fuzzy_match(axle_distances, true_axle_distances))
print("Groups match:",
      axle_groups == true_groups)
