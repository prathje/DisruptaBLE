import numpy

def format_dist(d):
    return numpy.format_float_scientific(d, unique=False, exp_digits=3, precision=6)

# Important: We need to iterate the same way as BabbleSim for the best efficiency
def iter_nodes(nr_nodes):
    for a in range(nr_nodes):
        for b in range(nr_nodes):
            if a > b:
                yield (a,b)