from random import choice

SIZE = 4
STATES = [1, 0]


class Square:

    def __init__(self, state=STATES[0]):
        self.state = state

    def __str__(self):
        return 'O' if self.state == STATES[0] else '+'

    def revert(self):
        self.state = STATES[STATES.index(self.state) - 1]

    def to_dict(self):
        return {"state": self.state}

    @classmethod
    def from_dict(cls, data):
        return cls(data["state"])


class Field:

    def __init__(self, size=SIZE, custom_squares=None):

        if custom_squares is not None:
            self.squares = custom_squares
            self.size = len(custom_squares)
        else:
            self.size = size
            self.squares = [[Square(choice(STATES)) for _ in range(self.size)] for _ in range(self.size)]
        self.steps = 0

    def even(self):
        for i in range(self.size):
            for j in range(self.size):
                if self.squares[0][0].state != self.squares[i][j].state:
                    return False
        return True

    def __str__(self):
        return '\n'.join([
                ' '.join(['+' if sq.state == STATES[0] else '0' for sq in row])
                for row in self.squares
            ]) + f'\n\nStep: {self.steps}'

    def revert(self, line, column):
        for i in range(self.size):
            self.squares[i][column].revert()
            self.squares[line][i].revert()
        self.squares[line][column].revert()
        self.steps = self.steps + 1

    def to_dict(self):
        return {
            "size": self.size,
            "steps": self.steps,
            "squares": [
                [sq.to_dict() for sq in row]
                for row in self.squares
            ]
        }

    @classmethod
    def from_dict(cls, data):
        squares = [
            [Square.from_dict(sq) for sq in row]
            for row in data["squares"]
        ]

        obj = cls(custom_squares=squares)
        obj.steps = data["steps"]
        return obj

    def matrix(self):
        return [[sq.state for sq in row] for row in self.squares]


# print(__name__)

if __name__ == '__main__':
    s = Field()
    a = {'1': [0, 0], '2': [0, 1], '3': [0, 2], '4': [0, 3],
         'q': [1, 0], 'w': [1, 1], 'e': [1, 2], 'r': [1, 3],
         'a': [2, 0], 's': [2, 1], 'd': [2, 2], 'f': [2, 3],
         'z': [3, 0], 'x': [3, 1], 'c': [3, 2], 'v': [3, 3]}
    print(s)
    while not s.even():
        x = input('letter ')
        s.revert(*a[x])
        print(s)
