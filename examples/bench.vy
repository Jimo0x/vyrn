# Mesure de performance : récursion + boucles serrées
fn fib(n: int) -> int:
    if n < 2: return n
    return fib(n - 1) + fib(n - 2)

fn primes(limit: int) -> int:
    var sieve: list[bool] = []
    for i in 0..limit + 1:
        sieve.push(true)
    var count = 0
    for i in 2..limit + 1:
        if sieve[i]:
            count += 1
            var j = i * i
            while j <= limit:
                sieve[j] = false
                j += i
    return count

fn main():
    let t0 = clock()
    print("fib(35) =", fib(35))
    print("nombres premiers < 10 000 000 :", primes(10000000))
    print("temps (s) :", clock() - t0)
