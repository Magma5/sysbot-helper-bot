from more_itertools import sliced


def to_ipv6(ip_bits):
    return ":".join(sliced(hex(ip_bits)[2:], 4))


def to_ipv4(ip_bits):
    return ".".join(str(0xFF & ip_bits >> i) for i in range(24, -1, -8))
