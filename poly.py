from curve import Scalar
from enum import Enum


class Basis(Enum):
    LAGRANGE = 1
    MONOMIAL = 2
    OFFSET_LAGRANGE = 3
    OFFSET_MONOMIAL = 4


class Polynomial:
    values: list[Scalar]
    basis: Basis

    def __init__(self, values: list[Scalar], basis: Basis):
        assert all(isinstance(x, Scalar) for x in values)
        assert isinstance(basis, Basis)
        self.values = values
        self.basis = basis

    def __eq__(self, other):
        return (self.basis == other.basis) and (self.values == other.values)

    def __add__(self, other):
        if isinstance(other, Polynomial):
            assert len(self.values) == len(other.values)
            assert self.basis == other.basis

            return Polynomial(
                [x + y for x, y in zip(self.values, other.values)],
                self.basis,
            )
        else:
            assert isinstance(other, Scalar)
            if self.basis == Basis.LAGRANGE or self.basis == Basis.OFFSET_LAGRANGE:
                return Polynomial(
                    [x + other for x in self.values],
                    self.basis,
                )
            else:
                return Polynomial(
                    [self.values[0] + other] + self.values[1:],
                    self.basis
                )

    def __sub__(self, other):
        if isinstance(other, Polynomial):
            assert len(self.values) == len(other.values)
            assert self.basis == other.basis

            return Polynomial(
                [x - y for x, y in zip(self.values, other.values)],
                self.basis,
            )
        else:
            assert isinstance(other, Scalar)
            if self.basis == Basis.LAGRANGE or self.basis == Basis.OFFSET_LAGRANGE:
                return Polynomial(
                    [x - other for x in self.values],
                    self.basis,
                )
            else:
                return Polynomial(
                    [self.values[0] - other] + self.values[1:],
                    self.basis
                )


    def __mul__(self, other):
        if isinstance(other, Polynomial):
            assert self.basis == Basis.LAGRANGE or self.basis == Basis.OFFSET_LAGRANGE
            assert self.basis == other.basis
            assert len(self.values) == len(other.values)

            return Polynomial(
                [x * y for x, y in zip(self.values, other.values)],
                self.basis,
            )
        else:
            assert isinstance(other, Scalar)
            return Polynomial(
                [x * other for x in self.values],
                self.basis,
            )

    def __truediv__(self, other):
        if isinstance(other, Polynomial):
            assert self.basis == Basis.LAGRANGE or self.basis == Basis.OFFSET_LAGRANGE
            assert self.basis == other.basis
            assert len(self.values) == len(other.values)

            return Polynomial(
                [x / y for x, y in zip(self.values, other.values)],
                self.basis,
            )
        else:
            assert isinstance(other, Scalar)
            return Polynomial(
                [x / other for x in self.values],
                self.basis,
            )

    def shift(self, shift: int):
        assert self.basis == Basis.LAGRANGE
        assert shift < len(self.values)

        return Polynomial(
            self.values[shift:] + self.values[:shift],
            self.basis,
        )

    # Convenience method to do FFTs specifically over the subgroup over which
    # all of the proofs are operating
    def fft(self, inv=False):
        # Fast Fourier transform, used to convert between polynomial coefficients
        # and a list of evaluations at the roots of unity
        # See https://vitalik.ca/general/2019/05/12/fft.html
        def _fft(vals, modulus, roots_of_unity):
            if len(vals) == 1:
                return vals
            L = _fft(vals[::2], modulus, roots_of_unity[::2])
            R = _fft(vals[1::2], modulus, roots_of_unity[::2])
            o = [0] * len(vals)
            for i, (x, y) in enumerate(zip(L, R)):
                y_times_root = y * roots_of_unity[i]
                o[i] = (x + y_times_root) % modulus
                o[i + len(L)] = (x - y_times_root) % modulus
            return o

        roots = [x.n for x in Scalar.roots_of_unity(len(self.values))]
        o, nvals = Scalar.field_modulus, [x.n for x in self.values]
        if inv:
            assert self.basis == Basis.LAGRANGE or self.basis == Basis.OFFSET_LAGRANGE
            if self.basis == Basis.LAGRANGE:
                new_basis = Basis.MONOMIAL
            elif self.basis == Basis.OFFSET_LAGRANGE:
                new_basis = Basis.OFFSET_MONOMIAL
            # Inverse FFT
            invlen = Scalar(1) / len(self.values)
            reversed_roots = [roots[0]] + roots[1:][::-1]
            return Polynomial(
                [Scalar(x) * invlen for x in _fft(nvals, o, reversed_roots)],
                new_basis,
            )
        else:
            assert self.basis == Basis.MONOMIAL or self.basis == Basis.OFFSET_MONOMIAL
            # Regular FFT
            if self.basis == Basis.MONOMIAL:
                new_basis = Basis.LAGRANGE
            elif self.basis == Basis.OFFSET_MONOMIAL:
                new_basis = Basis.OFFSET_LAGRANGE
            return Polynomial(
                [Scalar(x) for x in _fft(nvals, o, roots)], new_basis
            )

    def ifft(self):
        return self.fft(True)

    # Converts a list of evaluations at [1, w, w**2... w**(n-1)] to
    # a list of evaluations at
    # [offset, offset * q, offset * q**2 ... offset * q**(4n-1)] where q = w**(1/4)
    # This lets us work with higher-degree polynomials, and the offset lets us
    # avoid the 0/0 problem when computing a division (as long as the offset is
    # chosen randomly)
    def to_coset_extended_lagrange(self, offset):
        assert self.basis == Basis.LAGRANGE
        group_order = len(self.values)
        x_powers = self.ifft().values
        x_powers = [(offset**i * x) for i, x in enumerate(x_powers)] + [Scalar(0)] * (
            group_order * 3
        )
        return Polynomial(x_powers, Basis.OFFSET_MONOMIAL).fft()

    #Converts a list of coefficients to
    # a list of evaluations at
    # [offset, offset * q, offset * q**2 ... offset * q**(n-1)]
    def fft_to_coset_lagrange(self, offset):
        assert self.basis == Basis.MONOMIAL
        x_powers = [(offset**i * x) for i, x in enumerate(self.values)]
        return Polynomial(x_powers, Basis.OFFSET_MONOMIAL).fft()

    def lagrange_to_coset_lagrange(self, offset):
        assert self.basis == Basis.LAGRANGE
        return self.ifft().fft_to_coset_lagrange(offset)

    def lagrange_expand_to_coset_lagrange(self, offset):
        assert self.basis == Basis.LAGRANGE
        return self.to_coset_extended_lagrange(offset)

    # Convert from offset form into coefficients
    # Note that we can't make a full inverse function of to_coset_extended_lagrange
    # because the output of this might be a deg >= n polynomial, which cannot
    # be expressed via evaluations at n roots of unity
    def coset_extended_lagrange_to_coeffs(self, offset):
        assert self.basis == Basis.OFFSET_LAGRANGE

        shifted_coeffs = self.ifft().values
        inv_offset = 1 / offset
        return Polynomial(
            [v * inv_offset**i for (i, v) in enumerate(shifted_coeffs)],
            Basis.MONOMIAL,
        )

    def eval_coset_lagrange(self, x: Scalar, offset):
        assert self.basis == Basis.OFFSET_LAGRANGE
        return self.coset_extended_lagrange_to_coeffs(offset).fft().barycentric_eval(x)

    # Given a polynomial expressed as a list of evaluations at roots of unity,
    # evaluate it at x directly, without using an FFT to covert to coeffs first
    def barycentric_eval(self, x: Scalar):
        assert self.basis == Basis.LAGRANGE

        order = len(self.values)
        roots_of_unity = Scalar.roots_of_unity(order)
        return (
            (Scalar(x) ** order - 1)
            / order
            * sum(
                [
                    value * root / (x - root)
                    for value, root in zip(self.values, roots_of_unity)
                ]
            )
        )
