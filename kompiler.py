import sys
from dataclasses import dataclass as dk #datenklass
from typing import Any


def ZeichenEinOrdne(zeichen):
    match zeichen:
        case x if x.isdigit(): return "zahl"
        case x if x.isalpha(): return "wort"
        case '_':              return "wort"
        case ':':              return "wort"

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
    index  : int = 0

    def schau_marke(self):
        return self.marken[self.index]

    def schau(self):
        return self.schau_marke().inhalt

    def nimm(self):
        marke = self.schau()
        self.index += 1
        return marke

    def hat(self):
        return self.index < len(self.marken)

    def erwarte(self, soll):
        ist = self.schau_marke()
        if ist.inhalt != soll:
            print(f"Syntaxfehler in Zeile {ist.zeile}: Erwarte `{soll}`, aber habe `{ist.inhalt}` bekomment.")
            fuck()
            sys.exit(1)
        self.nimm()

def LexAnalyse(pfad):
    with open(pfad, 'r', encoding='utf-8') as f:
        quelle = f.read()

    puffer = []
    zeile = 1
    letzter_zustand = None
    kontrol_zeichen = False

    fluss = []
    for zeichen in quelle:
        dieser_zustand = ZeichenEinOrdne(zeichen)
        
        if zeichen == '\n':
            zeile += 1

        if kontrol_zeichen:
            puffer.pop(-1)
            match zeichen:
                case '0': puffer.append('\0')
            kontrol_zeichen = False
            continue

        if letzter_zustand and dieser_zustand != letzter_zustand:
            if letzter_zustand != "formatierung":
                fluss.append(Marke("".join(puffer), zeile))

            puffer = []

        puffer.append(zeichen)
        letzter_zustand = dieser_zustand
        kontrol_zeichen = (zeichen == '\\')

    return Fluss(fluss)


@dk
class AsbAufruf:
    name : str
    parameter : Any

    @classmethod
    def zerteil(kls, fluss, name):
        fluss.erwarte("(")

        parameter = []
        while fluss.schau() != ')':
            parameter.append(AsbBinär.zerteil(fluss))
            if fluss.schau() == ',':
                fluss.nimm()

        fluss.erwarte(")")
        return kls(name, parameter)





OPERATOREN = ['+', '-', '*', '/', '.', '<<', '>>', '&', '|', '^', '==', '!=', '>', '<']

@dk
class AsbUnär:
    art : str
    inhalt : Any

    @classmethod
    def zerteil(kls, fluss):
        match fluss.nimm():
            case zahl if zahl.isdigit():
                art = "zahl"
                inhalt = int(zahl)
            case '(':
                unterausdruck = AsbBinär.zerteil(fluss)
                fluss.erwarte(')')
                return unterausdruck

            case '›':
                art = "zeichen"
                inhalt = fluss.nimm()
                fluss.erwarte('‹')

            case '-':
                art = "minus"
                inhalt = AsbUnär.zerteil(fluss)

            case name if fluss.schau() == '(':
                art = "aufruf"
                inhalt = AsbAufruf.zerteil(fluss, name)

            case wort:
                art = "zugriff"
                inhalt = wort


        return kls(art, inhalt)




@dk
class AsbBinär:
    links  : Any
    rechts : Any
    operator : str

    @classmethod
    def zerteil(kls, fluss):
        links = AsbUnär.zerteil(fluss)
        operator = fluss.schau()

        if operator not in OPERATOREN:
            return links

        fluss.nimm()
        rechts = AsbBinär.zerteil(fluss)
        return kls(links, rechts, operator)

@dk
class AsbTu:
    variable : str
    quelle   : AsbBinär

    @classmethod
    def zerteil(kls, fluss):
        fluss.erwarte("tu")
        variable = fluss.nimm()
        fluss.erwarte("=")
        quelle = AsbBinär.zerteil(fluss)
        fluss.erwarte(";")
        return kls(variable, quelle)


@dk
class AsbRück:
    ziel : AsbBinär

    @classmethod
    def zerteil(kls, fluss):
        fluss.erwarte("rück")
        ziel = AsbBinär.zerteil(fluss)
        fluss.erwarte(";")
        return kls(ziel)

@dk
class AsbSolang: 
    bedingung : AsbBinär
    körper    : "AsbAbschnitt"

    @classmethod
    def zerteil(kls, fluss):
        fluss.erwarte("solang")
        bedingung = AsbBinär.zerteil(fluss)
        körper    = AsbAbschnitt.zerteil(fluss)
        return kls(bedingung, körper)

@dk
class AsbFalls: 
    bedingung : AsbBinär
    körper    : "AsbAbschnitt"

    @classmethod
    def zerteil(kls, fluss):
        fluss.erwarte("falls")
        bedingung = AsbBinär.zerteil(fluss)
        körper    = AsbAbschnitt(fluss)
        return kls(bedingung, körper)

@dk
class AsbAusdruck: 
    ziel : AsbBinär

    @classmethod
    def zerteil(kls, fluss):
        ziel = AsbBinär.zerteil(fluss)
        fluss.erwarte(";")
        return kls(ziel)


@dk
class AsbAussage:
    @classmethod
    def zerteil(kls, fluss):
        match fluss.schau():
            case 'tu'    : return AsbTu.zerteil(fluss)
            case 'rück'  : return AsbRück.zerteil(fluss)
            case 'solang': return AsbSolang.zerteil(fluss)
            case 'falls' : return AsbFalls.zerteil(fluss)
            case _       : return AsbAusdruck.zerteil(fluss)


@dk
class AsbAbschnitt:
    aussagen: list[Any]

    @classmethod
    def zerteil(kls, fluss):
        fluss.erwarte("auf")

        aussagen = []
        while fluss.schau() != "zu":
            aussagen.append(AsbAussage.zerteil(fluss))

        fluss.erwarte("zu")
        return kls(aussagen)


@dk
class AsbProzedur:
    name : str
    parameter : list[str]
    körper : AsbAbschnitt

    @classmethod
    def zerteil(kls, fluss):
        fluss.erwarte('prozedur')
        name = fluss.nimm()
        fluss.erwarte('(')

        parameter = []
        while fluss.schau() != ')':
            parameter.append(fluss.nimm())
            if fluss.schau() == ',':
                fluss.nimm()

        fluss.erwarte(')')
        körper = AsbAbschnitt.zerteil(fluss)
        return kls(name, parameter, körper)


@dk
class AsbProgramm:
    prodezuren : list[AsbProzedur]
    konstantent : dict[str, int]

    @classmethod
    def zerteil(kls, fluss):
        prozeduren  = []
        konstantent = {}

        while fluss.hat():
            match fluss.schau():
                case 'prozedur':  
                    prozeduren.append(AsbProzedur.zerteil(fluss))
                case 'konstant':  
                    fluss.nimm()
                    name = fluss.nimm()
                    fluss.erwarte("=")
                    wert = AsbBinär.zerteil(fluss)
                    fluss.erwarte(";")

                    konstantent[name] = wert
                case wort:
                    print(f"Unbekannes Hauptwort: `{wort}`")
                    sys.exit(1)

        return kls(prozeduren, konstantent)


def Haupt():
    pfad  = sys.argv[1]
    fluss = LexAnalyse(pfad)
    wurzel = AsbProgramm.zerteil(fluss)
    print(wurzel)



if __name__ == "__main__":
    Haupt()

