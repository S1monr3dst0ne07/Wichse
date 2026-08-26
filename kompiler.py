from dataclasses import dataclass as dk #datenklass
from dataclasses import field     as feld
from typing import Any
import subprocess
import tempfile
import sys, os


def ZeichenEinOrdne(zeichen):
    match zeichen:
        case x if x.isdigit(): return "zahl"
        case x if x.isalpha(): return "wort"
        case '_':              return "wort"
        case '§':              return "wort"

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
            sys.exit(1)
        self.nimm()

def LexAnalyse(pfad):
    with open(pfad, 'r', encoding='utf-8') as f:
        quelle = f.read()

    puffer = []
    zeile = 1
    letzter_zustand = None
    kontrol_zeichen = False
    zeichenketten_tiefe = 0

    fluss = []
    for zeichen in quelle:
        dieser_zustand = ZeichenEinOrdne(zeichen)
        
        if zeichen == '\n': zeile += 1

        if kontrol_zeichen:
            puffer.pop(-1)
            match zeichen:
                case '0': puffer.append('\0')
                case 'z': puffer.append('\n')
            kontrol_zeichen = False
            continue

        abgeben = True
        abgeben &= bool(letzter_zustand)
        abgeben &= (dieser_zustand != letzter_zustand)
        abgeben &= (zeichenketten_tiefe == 0)

        if abgeben or (zeichen in ('(', ')')):
            if letzter_zustand != "formatierung":
                fluss.append(Marke("".join(puffer), zeile))

            puffer = []

        if zeichen == '»' : zeichenketten_tiefe += 1
        if zeichen == '«' : zeichenketten_tiefe -= 1

        puffer.append(zeichen)
        letzter_zustand = dieser_zustand
        kontrol_zeichen = (zeichen == '\\')

    return Fluss(fluss)


def ProzedurName(name):
    name_sauber = name.translate({
        ord(':') : ord('_'),
    })
    return f"Prozedur_{name_sauber}"


REGISTER = ['rcx', 'rdx', 'r8', 'r9']


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

    def zusammenstell(selbst, gk, gib):
        schnell_teil = selbst.parameter[:4]
        stapel_teil  = selbst.parameter[4:]

        dynamisch, prozedur = gk.schlage_prozedur_nach(selbst.name)
        pgrößen = prozedur.parameter_größen

        # lade schnelle parameter in die übergaberegister
        register = REGISTER[:len(schnell_teil)]
        for ausdruck in schnell_teil:
            ausdruck.lade(gk, gib)
            gib("push rax")
        for ziel in register[::-1]:
            gib(f"pop {ziel}")

        # versichere, dass der Stack aligned ist,
        # und dass die Schattenregion existiert.
        gib("push rbp")
        gib("mov  r10, rsp") #r10 darf für NICHTS anderes benutzt werden!
        gib("and  rsp, -16")
        gib("sub  rsp, 20h")

        for index, rest in enumerate(stapel_teil):
            pindex = index + 4
            if pindex < len(pgrößen):
                fehler("Prozeduraufruf hat mehr Parameter als Prozedursignatur.")

            rest.lade(gk, gib)
            match pgrößen[pindex]:
                case 1: gib("push al")
                case 2: gib("push ax")
                case 4: gib("push eax")
                case 8: gib("push rax")

        #base pointer wird verzögert gesetzt,
        # damit die stapel parameter errechnet werden können.
        gib("mov rbp, r10") 
        
        besch = ProzedurName(selbst.name)
        if dynamisch: gib(f"call [{besch}]")
        else:         gib(f"call  {besch} ")

        gib("mov  rsp, rbp")
        gib("pop  rbp")



def fehler(msg):
    print(f"Fehler: {msg}")
    sys.exit(1)


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
                inhalt = ord(fluss.nimm())
                fluss.erwarte('‹')

            case zk if zk.startswith("»"):
                art = "zk"
                inhalt = zk.strip("»«")
            case '-':
                art = "minus"
                inhalt = AsbUnär.zerteil(fluss)
            case '*':
                art = "zeiger"
                inhalt = AsbBinär.zerteil(fluss)
            case '&':
                art = "addresse"
                inhalt = AsbBinär.zerteil(fluss)

            case name if fluss.schau() == '(':
                art = "aufruf"
                inhalt = AsbAufruf.zerteil(fluss, name)

            case wort:
                art = "variable"
                inhalt = wort


        return kls(art, inhalt)

    def lokale(selbst, menge):
        if selbst.art == "variable":
            menge.add(selbst.inhalt)

    def lade(selbst, gk, gib):
        match selbst.art:
            case 'zahl' | 'zeichen': 
                gib(f"mov rax, {selbst.inhalt}")
            case 'minus':
                selbst.inhalt.lade(gk, gib)
                gib("neg rax")
            case 'variable':
                if selbst.inhalt in gk.variablen:
                    virtuelle_addresse = gk.variablen[selbst.inhalt]
                    gib(f"mov rax, [rbp-{virtuelle_addresse}]")
                    return
                if selbst.inhalt in gk.wurzelknoten.konstantent:
                    gk.wurzelknoten.konstantent[selbst.inhalt].lade(gk, gib)
                    return

                resultat = len(gk.suche_schema_beim_namen(selbst.inhalt).felder)
                if resultat is not None:
                    gib(f"mov rax, {resultat}")
                    return

                fehler(f"Versuchte das Symbol `{selbst.inhalt}` zu laden, aber dieses wurde nicht definiert.")


            case 'zeiger':
                selbst.inhalt.lade(gk, gib)
                gib("mov rax, [rax]")
            case 'aufruf':
                selbst.inhalt.zusammenstell(gk, gib)
            case 'zk':
                zk_beschriftung = gk.frisch()
                gk.zk[zk_beschriftung] = selbst.inhalt
                gib(f"mov rax, {zk_beschriftung}")

    def speicher(selbst, gk, gib):
        match selbst.art:
            case 'zahl':   fehler("Versuchte eine Zahl zu überschreiben.")
            case 'zeichen':fehler("Versuchte eine Zeichenkonstante zu überschreiben.")
            case 'minus':  fehler("Versuchte einen Minusausdruck zu überschreiben.")
            case 'variable':
                virtuelle_addresse = gk.variablen[selbst.inhalt]
                gib(f"mov [rbp-{virtuelle_addresse}], rax")
            case 'zeiger':
                gib('push rax')
                selbst.inhalt.lade(gk, gib)
                gib('pop rbx')
                gib('mov [rax], rbx')




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

    def lokale(selbst, menge):
        pass

    def lade(selbst, gk, gib):
        selbst.rechts.lade(gk, gib)
        gib("push rax")
        selbst.links.lade(gk, gib)
        gib("pop rbx")

        match selbst.operator:
            case '+': gib("add rax, rbx")
            case '-': gib("sub rax, rbx")
            case '*': gib("mul rbx")
            case '&': gib("and rax, rbx")

            case '!=':
                gib("cmp rax, rbx")
                gib("setne cl")
                gib("movzx rax, cl")

            case op:
                print(f"IMPL. OP. {op}")

    def speicher(selbst, gk, gib):
        match selbst.operator:
            case '.':
                links = selbst.links
                rechts = selbst.rechts
                schemabezeichnung = rechts.inhalt

                if rechts.art != "variable":
                    fehler("Rechte Seite eines Punktausrucks ist keine Variable.")
                if "§" not in schemabezeichnung:
                    fehler(f"Unbekannte Schemabezeichnung: `{schemabezeichnung}`")

                schemaname, schemafeld = schemabezeichnung.split("§")
                schema = gk.suche_schema_beim_namen(schemaname)
                if schemafeld not in schema.felder:
                    fehler(f"Das Schemafeld `{schemafeld}` ist nicht present in `{schemaname}`")
                index = schema.felder.index(schemafeld)
                größe = schema.größen[index]
                verschiebung = sum(schema.größen[:index])

                gib("push rax")
                selbst.links.lade(gk, gib)
                gib(f"add rax, {verschiebung}")
                gib("pop rbx")
                match größe:
                    case 8: gib("mov [rax], rbx")
                    case 4: gib("mov [rax], ebx")

                    case x:
                        fehler(f"Felder der Größe {x} bytes nicht unterstützt.")

            case _:
                fehler("Versuchte in einen nicht-Punktausdruck einzuspeichern.")



@dk
class AsbTu:
    ziel   : AsbBinär
    quelle : AsbBinär

    @classmethod
    def zerteil(kls, fluss):
        fluss.erwarte("tu")
        variable = AsbBinär.zerteil(fluss)
        fluss.erwarte("=")
        quelle = AsbBinär.zerteil(fluss)
        fluss.erwarte(";")
        return kls(variable, quelle)

    def lokale(selbst, menge):
        selbst.ziel.lokale(menge)

    def zusammenstell(selbst, gk, gib):
        selbst.quelle.lade(gk, gib)
        selbst.ziel.speicher(gk, gib)



@dk
class AsbRück:
    ziel : AsbBinär

    @classmethod
    def zerteil(kls, fluss):
        fluss.erwarte("rück")
        ziel = AsbBinär.zerteil(fluss)
        fluss.erwarte(";")
        return kls(ziel)

    def lokale(selbst, _):
        pass

    def zusammenstell(selbst, gk, gib):
        selbst.ziel.lade(gk, gib)
        gib("leave")
        gib("ret")

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

    def lokale(selbst, menge):
        selbst.körper.lokale(menge)

    def zusammenstell(selbst, gk, gib):
        überspring_beschriftung = gk.frisch()
        schleifen_beschriftung  = gk.frisch()

        gib(f"{schleifen_beschriftung}:")
        selbst.bedingung.lade(gk, gib)
        gib(f"cmp rax, 0")
        gib(f"je {überspring_beschriftung}")

        selbst.körper.zusammenstell(gk, gib)

        gib(f"jmp {schleifen_beschriftung}")
        gib(f"{überspring_beschriftung}:")


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

    def lokale(selbst, menge):
        selbst.körper.lokale(menge)

@dk
class AsbAusdruck: 
    ziel : AsbBinär

    @classmethod
    def zerteil(kls, fluss):
        ziel = AsbBinär.zerteil(fluss)
        fluss.erwarte(";")
        return kls(ziel)

    def lokale(selbst, _):
        pass

    def zusammenstell(selbst, gk, gib):
        selbst.ziel.lade(gk, gib)


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

    def lokale(selbst, menge):
        for aussage in selbst.aussagen:
            aussage.lokale(menge)

    def zusammenstell(selbst, gk, gib):
        for aussage in selbst.aussagen:
            aussage.zusammenstell(gk, gib)


@dk
class AsbProzedur:
    name : str
    parameter_namen  : list[str]
    parameter_größen : list[int]
    körper : AsbAbschnitt

    @classmethod
    def zerteil(kls, fluss):
        fluss.erwarte('prozedur')
        name = fluss.nimm()
        fluss.erwarte('(')

        pnamen = [] 
        pgrößen = []

        while fluss.schau() != ")":
            pname = fluss.nimm()
            fluss.erwarte(":")
            pgröße = int(fluss.nimm())
            if fluss.schau() == ",": fluss.nimm()

            pnamen.append(pname)
            pgrößen.append(pgröße)


        fluss.erwarte(')')
        körper = AsbAbschnitt.zerteil(fluss)
        return kls(name, pnamen, pgrößen, körper)

    def zusammenstell(selbst, gk, gib):
        gib(ProzedurName(selbst.name) + ":")
        lokale_variablen_menge = set(selbst.parameter_namen)
        selbst.körper.lokale(lokale_variablen_menge)
        lokale_variablen = len(lokale_variablen_menge)

        gk.variablen = { name : (vaddr+1) * 8 for vaddr,name in enumerate(lokale_variablen_menge) }

        gib(f"enter {8*lokale_variablen}, 0")

        register = REGISTER[:len(selbst.parameter_namen)]
        for name, quelle in zip(selbst.parameter_namen, register):
            virtuelle_addresse = gk.variablen[name]
            gib(f"mov [rbp-{virtuelle_addresse}], {quelle}")

        selbst.körper.zusammenstell(gk, gib)
        gib("leave")
        gib("ret")


@dk
class GlobalerKontext:
    wurzelknoten : Any
    variablen   : dict[str, int] = None
    zk          : dict[str, str] = feld(default_factory=lambda: {})
    __frisch_index : int = 0

    def frisch(selbst):
        selbst.__frisch_index += 1
        return f"__Frisch_{selbst.__frisch_index}"

    def suche_schema_beim_namen(selbst, name):
        for schema in selbst.schemata:
            if schema.name == name:
                return schema

    def suche_externe_beim_namen(selbst, name):
        for extern in selbst.externe:
            if extern.name == name:
                return extern

    def schlage_prozedur_nach(selbst, name):
        print(name)
        for intern in selbst.wurzelknoten.prozeduren:
            if intern.name == name:
                return False, intern

        for extern in selbst.wurzelknoten.externe:
            if extern.name == name:
                return True, extern

        fehler(f"Prozedur mit dem namen `{name}` wurde nicht gefunden.")


@dk
class AsbExtern:
    name : str
    parameter_namen : list[str]
    parameter_größen : list[int]

    außenname : str
    buch      : str

    @classmethod
    def zerteil(kls, fluss):
        fluss.erwarte("externe")
        fluss.erwarte("prozedur")
        name = fluss.nimm()
        fluss.erwarte("(")

        pnamen = [] 
        pgrößen = []

        while fluss.schau() != ")":
            pname = fluss.nimm()
            fluss.erwarte(":")
            pgröße = int(fluss.nimm())
            if fluss.schau() == ",": fluss.nimm()

            pnamen.append(pname)
            pgrößen.append(pgröße)

        fluss.erwarte(")")
        fluss.erwarte("heißt")
        außenname = fluss.nimm().strip("»«")
        fluss.erwarte("von")
        buch = fluss.nimm().strip("»«")

        return kls(name, pnamen, pgrößen, außenname, buch)



@dk
class AsbSchema:
    name   : str
    felder : list[str]
    größen : list[int]

    @classmethod
    def zerteil(kls, fluss):
        felder = []
        größen = []

        fluss.erwarte("schema")
        name = fluss.nimm()
        fluss.erwarte("auf")

        while fluss.schau() != "zu":
            feld = fluss.nimm() 
            fluss.erwarte(":")
            größe = int(fluss.nimm())

            if fluss.schau() == ",":
                fluss.erwarte(",")

            felder.append(feld)
            größen.append(größe)

        fluss.erwarte("zu")

        return kls(name, felder, größen)





bekannte_programm_pfad = set()

@dk
class AsbProgramm:
    prozeduren  : list[AsbProzedur]
    konstantent : dict[str, int]
    schemata    : list
    externe     : list


    @classmethod
    def analysis(kls, pfad):
        fluss = LexAnalyse(pfad)
        return kls.zerteil(fluss)

    @classmethod
    def zerteil(kls, fluss):
        prozeduren  = []
        konstantent = {}
        schemata    = []
        externe     = []

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
                case 'schließ':
                    fluss.erwarte("schließ")
                    pfad = fluss.nimm().strip("»«")
                    fluss.erwarte("ein")

                    if pfad in bekannte_programm_pfad:
                        continue

                    bekannte_programm_pfad.add(pfad)
                    unterwurzel = kls.analysis(pfad)

                    prozeduren  +=     unterwurzel.prozeduren
                    schemata    +=     unterwurzel.schemata
                    externe     +=     unterwurzel.externe
                    konstantent.update(unterwurzel.konstantent)

                case 'schema':
                    schemata.append(AsbSchema.zerteil(fluss))

                case 'externe':
                    externe.append(AsbExtern.zerteil(fluss))

                case wort:
                    print(f"Unbekannes Hauptwort: `{wort}`")
                    sys.exit(1)

        return kls(prozeduren, konstantent, schemata, externe)

    def zusammenstell(selbst, gib):
        gk = GlobalerKontext(selbst)
        print(selbst)
        print(gk)
        
        gib("format PE64")
        gib("entry start")
        gib("section '.text' code readable executable")
        gib("start:")
        gib(f"call {ProzedurName('Haupt')}")
        gib("hlt")

        for prozedur in selbst.prozeduren:
            prozedur.zusammenstell(gk, gib)

        gib("section '.data' data readable writeable")
        gib("platzhalter db 0") #.data sektion kann nich leer sein
        for name, zk in gk.zk.items():
            daten = ','.join(str(ord(zeichen)) for zeichen in zk + '\0')
            gib(f"{name} db {daten}")


        externe_bücher = {}
        externe_proz_namen = {} 
        externe_buch_namen = {} 

        # sammle alle bücher, und erzeuge tabellen. geil.
        for extern in gk.wurzelknoten.externe:
            if extern.buch not in externe_bücher:
                externe_bücher[extern.buch] = (
                    gk.frisch(), #buchbeschriftung
                    [], #prozeduren
                )

            _, prozen = externe_bücher[extern.buch]
            prozen.append(extern)

        # windows. wir alle hassen es.
        gib("section '.idata' import data readable writeable")
        for name, buch in externe_bücher.items():
            besch = gk.frisch()
            externe_buch_namen[besch] = name
            gib(f"dd  0,0,0,RVA {besch},RVA {buch[0]}")
        gib("dd  0,0,0,0,0")

        for besch, prozen in externe_bücher.values():
            gib(f"{besch}:")
            for proz in prozen:
                besch = gk.frisch()
                gib(f"   Prozedur_{proz.name} dq RVA {besch}")
                externe_proz_namen[besch] = proz.außenname
            gib("dq 0")

        # namen zeichenketten
        for buch_besch, buch_name in externe_buch_namen.items():
            gib(f"{buch_besch} db '{buch_name}',0")
        for proz_besch, proz_name in externe_proz_namen.items():
            gib(f"{proz_besch} db 0,0,'{proz_name}',0")




def Haupt():
    pfad  = sys.argv[1]
    wurzel = AsbProgramm.analysis(pfad)

    zusammenbau = []
    gib = lambda x: zusammenbau.append(x)

    wurzel.zusammenstell(gib)
    ausgabe = "\n".join(zusammenbau)
    print(ausgabe)

    hintergriff, hinterpfad = tempfile.mkstemp(suffix=".asm")
    try:
        with os.fdopen(hintergriff, "w", encoding="utf-8") as griff:
            griff.write(ausgabe)

        subprocess.run(["FASM.EXE", hinterpfad, "BAUWERK.EXE"])
    finally:
        os.remove(hinterpfad)


if __name__ == "__main__":
    Haupt()

