"""Bounded plot geometry that retains extrema and real time spacing."""
def plot_samples(values, timestamps=None, limit=600):
    if not values:
        return []
    count = len(values)
    if timestamps is not None and len(timestamps) != count:
        raise ValueError('The number of timestamps does not match the number of measurements.')
    indices = list(range(count))
    if count > limit:
        indices = [0, count-1]
        buckets = max(1, (limit-2)//2)
        for bucket in range(buckets):
            first = 1 + bucket*(count-2)//buckets
            last = 1 + (bucket+1)*(count-2)//buckets
            candidates = range(first, last)
            indices.extend((min(candidates, key=values.__getitem__), max(candidates, key=values.__getitem__)))
        indices = sorted(set(indices))
    if count == 1:
        return [(0.5, values[0])]
    span = timestamps[-1]-timestamps[0] if timestamps else 0
    return [(((timestamps[i]-timestamps[0])/span if span > 0 else i/(count-1)), values[i]) for i in indices]
