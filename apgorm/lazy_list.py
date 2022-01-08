# MIT License
#
# Copyright (c) 2021 TrigonDev
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

from typing import (
    Any,
    Callable,
    Generator,
    Generic,
    Sequence,
    TypeVar,
    overload,
)

_IN = TypeVar("_IN")
_OUT = TypeVar("_OUT")


class LazyList(Generic[_IN, _OUT]):
    def __init__(
        self,
        data: Sequence[_IN] | LazyList[Any, _IN],
        converter: Callable[[_IN], _OUT],
    ) -> None:
        self._data = data
        self._converter = converter

    def _convert(self, values: Sequence[_IN] | None = None) -> list[_OUT]:
        _values = self._data if not values else values
        return [self._converter(v) for v in _values]

    @overload
    def __getitem__(self, index: int) -> _OUT:
        ...

    @overload
    def __getitem__(self, index: slice) -> list[_OUT]:
        ...

    def __getitem__(self, index: int | slice) -> list[_OUT] | _OUT:
        if isinstance(index, int):
            return self._convert([self._data[index]])[0]
        return self._convert(self._data[index])

    def __iter__(self) -> Generator[_OUT, None, None]:
        for r in self._data:
            yield self._converter(r)

    def __list__(self) -> list[_OUT]:
        return self._convert()

    def __len__(self) -> int:
        return len(self._data)

    def __repr__(self) -> str:
        if len(self) > 5:
            ddd = ", ..."
        else:
            ddd = ""
        return "LazyList([{}{}])".format(
            ", ".join([repr(c) for c in self._convert(self._data[0:5])]),
            ddd,
        )
