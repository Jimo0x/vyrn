# Structs, listes de structs et chaînes
struct Article:
    nom: str
    prix: float
    stock: int

fn valeur(a: Article) -> float:
    return a.prix * a.stock

fn main():
    var stock: list[Article] = []
    let lignes = "clavier;49.9;12|souris;19.5;30|ecran;189;4".split("|")
    for l in lignes:
        let c = l.split(";")
        stock.push(Article(c[0], float(c[1]), int(c[2])))

    var total = 0.0
    for a in stock:
        print(a.nom.upper(), "->", valeur(a))
        total += valeur(a)
    print("valeur totale :", total)
    print(stock[0])
