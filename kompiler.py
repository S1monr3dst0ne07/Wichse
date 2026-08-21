import sys
from dataclasses import dataclass as dk #datenklass


def ZeichenEinOrdne(zeichen):
    match zeichen:
        case x if x.isdigit(): return "zahl"
        case x if x.isalpha(): return "wort"
        case '_':              return "wort"

        #Klammern müssen immer direkt
        # als Marken abgegeben werden. 
        case '(':              return "klammer auf"
        case ')':              return "klammer zu"

        case '»':              return "gänsefuß auf"
        case '«':              return "gänsefuß zu"

        case '›' | '‹':        return "gänsezeh"

        case ' ' | '\n':       return "formatierung"

        case _: return "symbol"


@dk
class Marke:
    inhalt : str
    zeile  : int
    
@dk
class Fluss:
    marken : list[Marke]
    index  : int

    def schau(self):
        return self.marken[self.index]

    def nimm(self):
        marke = self.schau()
        self.index += 1
        return marke

    def hat(self):
        return self.index < len(self.marken)


def LexAnalyse(pfad):
    with open(pfad, 'r', encoding='utf-8') as f:
        quelle = f.read()

    puffer = ""
    zeile = 0
    letzter_zustand = None

    fluss = []
    for zeichen in quelle:
        dieser_zustand = ZeichenEinOrdne(zeichen)

        if letzter_zustand and dieser_zustand != letzter_zustand:
            if letzter_zustand != "formatierung":
                fluss.append(Marke(puffer, zeile))

            puffer = ""

        puffer += zeichen
        letzter_zustand = dieser_zustand

    return fluss

class AsbProgramm:
    prodezuren : list[AsbProzedur]
    konstantent : dict[str, int]

    def zerteil(kls, fluss):
        prodezuren  = []
        konstantent = {}

        while fluss.hat():
            match fluss.schau():
                case 'prozedur':  prodezuren.append(AsbProzedur.zerteil(fluss))
                case 'konstant':  
                    name = fluss.nimm()
                    fluss.erwarte("=")
                    wert = int(fluss.nimm())

                    konstant[name] = wert

        return kls(prozeduren, konstantent)


def Haupt():
    pfad  = sys.argv[1]
    fluss = LexAnalyse(pfad)
    wurzel = AsbProgramm.zerteil(fluss)
    print(wurzel)



if __name__ == "__main__":
    Haupt()

