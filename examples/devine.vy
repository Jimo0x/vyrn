# Jeu : devine le nombre
fn main():
    let secret = rand_int(1, 100)
    var essais = 0
    print("J'ai choisi un nombre entre 1 et 100.")
    while true:
        let saisie = input("Ton choix : ")
        if saisie == "":
            print("Abandon. C'était", secret)
            return
        let n = int(saisie)
        essais += 1
        if n < secret:
            print("Plus grand !")
        elif n > secret:
            print("Plus petit !")
        else:
            print("Bravo, trouvé en", essais, "essais.")
            return
