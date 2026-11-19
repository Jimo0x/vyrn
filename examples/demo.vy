# Tour rapide de Vyrn
cinclude "math.h"

struct Point:
    x: float
    y: float

fn dist(a: Point, b: Point) -> float:
    let dx = a.x - b.x
    let dy = a.y - b.y
    return sqrt(dx * dx + dy * dy)

fn fib(n: int) -> int:
    if n < 2: return n
    return fib(n - 1) + fib(n - 2)

fn main():
    let p = Point(0.0, 0.0)
    let q = Point(3, 4)
    print("distance :", dist(p, q))
    print("point :", q)

    var nums: list[int] = []
    for i in 0..10:
        nums.push(i * i)
    print("carrés :", nums)

    var total = 0
    for n in nums:
        if n % 2 == 0:
            total += n
    print("somme des carrés pairs :", total)

    let mots = "le langage vyrn est rapide".split(" ")
    for m in mots:
        print(m.upper(), len(m))

    print("fib(30) =", fib(30))
