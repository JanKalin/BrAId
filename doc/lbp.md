

# Navodila za uporabo LBP (Label Braid Photos)

Jan Kalin <jan.kalin@zag.si>

v1.0, 20. Marec 2024

## Uvod

Ta dokument opisuje uporabo vizualne aplikacije Label Braid Photos, ki se uporablja za označevanje fotografij vozil stehtanih z SiWIM B-WIM. Namen aplikacije je označiti napačno označene fotografije, skupaj z napačno detektiranimi vozili, da se zgenerira "ground truth" nabor podatkov za učenje AI.

## Namestitev

### Python

Aplikacija je napisana v Pythonu in testirana z verzijo 3.9. Načeloma bi novejše verzije morale tudi podpirati to aplikacijo. Prvi korak je torej inštalacija Pythona.

### Zunanje Python knjižnice

Poleg knjižnic, ki se inštalirajo kot del osnovne inštalacije Pythona, aplikacija uporablja še zunanje knjižnice: `matplotlib`, `PyQt5`, `numpy` in `pandas`. Te je treba inštalirati, detajli so odvisni od distribucije Pythona.

### Lokalne Python knjižnice

Za branje SiWIM binarnih datotek se uporablja `siwim-pi`. Dostopen je na `M:\disk_600_konstrukcije\JanK\siwim-pi`. Če se poganja aplikacijo direktno z diska `M:`, inštalacija ni potrebna, drugače se odpre `cmd` v tem direktoriju in požene `pip install .` (pika je pomembna).

### Skripta in podatki

Skripta se nahaja na `M:\disk_600_konstrukcije\JanK\braid_photo\label_braid_photo.py`. 

V direktoriju `M:\disk_600_konstrukcije\JanK\braid_photo\data` so podatki:

- `*.nswd` v katerih so podatki o stehtanih vozilih
- `recognized_vehicles.json` vsebuje podatke o vozilih, ki jih je kategorizirala AI aplikacija
- `vehicle2event.json` vsebuje povezavo med vozilom in *event*-om — binarno datoteko v kateri so shranjeni signali in ostala informacija.
- Najpomembnejša datoteka je `metadata.hdf5`, v katero se shranjujejo rezultati ročnega označevanja vozil. Če se izgubi ali pokvari ta datoteka, bo ves do tedaj vložen trud zaman.

Če je Python pravilno inštaliran, bi moral dvoklik na skripto le-to zagnati.

### Predpriprava na zagon

Za polno funkcionalnost aplikacije je treba priklopiti nekaj omrežnih diskov pod točno določenimi imeni:

- `\\mn-620-modeli.zag.si\siwim` kot `S:`
- `\\mn-620-modeli.zag.si\nfssiwim` kot `T:`
- `\\mn-620-modeli.zag.si\braid` kot `B:`

V kolikor ne morete priklopiti diskov se oglasite pri avtorju.

## Uporaba aplikacije

### Zagon

Pri zagonu aplikacije se odpre konzola (`CMD` okno), v katerem se najprej izpiše

```
Loading recognized_vehicles.json, done.
Loading vehicle2event.json, done.
```

potem pa se pojavi glavno okno aplikacije. 

Konzole ne zapirajte, saj se s tem zapre tudi glavno okno.  V konzoli se tudi izpišejo nekatere napake pri izvajanju (recimo da neke datoteke ne more najti), pa tudi, če pride do kakšne napake pri samem izvajanju aplikacije.

Če se zgodi to, prosim avtorju pošljite screenshot konzole in opis tega, kaj ste delali, ko je do napake prišlo.

### Glavno okno

![main_window](main_window.png)

#### Meni

V meniju sta dve postavki. `Photo` vsebuje postavke za premikanje po fotografijah in nastavljanje oznak, vendar so vse postavke dosegljive tudi s pomočjo bližnjic. Za hitro pomoč je spisek  bližnjic dosegljiv v meniju `Help|Shortcuts`.

#### *Select vehicle groups for labelling*

![select](select.png)

Tukaj se izbere množico vozil za označevanje. Struktura podatkov o slikah je bila določena na FAMNIT na osnovi uporabe AI klasifikacije slik, tega se drži tudi aplikacija. Glavni nivo je delitev na avtobuse in tovornjake, kar se izbere z izbirnim gumbom *Busses* ali *Trucks*. Znotraj tega je delitev na skupine osi vozil. Primer je 113, ki predstavlja klasičen vlačilec s polpriklopnikom (šleper po domače). 

Če smo že pregledovali slike, lahko uporabimo potrditveno polje *Only unseen* in s tem omogočimo nalaganje samo tistih slik, ki jih še noben ni videl.

Ko je slika naložena, jo je možno s klikom na *Show photo in viewer* naložiti v eksterni pregledovalnik slik.

#### *ADMPs*

V tem razdelku se lahko vidi signale iz detektorjev osi. Primer je na sledeči sliki.

![ADMPs](ADMPs.png)

Zgornji graf je za pas 1, spodnji za pas 2. Na grafih je z modro narisan originalni signal, z oranžno filtriran signal, s črnimi črtami detektirane osi, ter z zeleno črto timestamp obravnavanega vozila.

Z odkljukanim izbirnim poljem *Auto load ADMPs* se signali naložijo avtomatično, skupaj s sliko. Drugače je potrebno pritisniti `<Alt>-D`.

S tipkama *Show ADMP event in viewer* in *Show CF event in viewer* se lahko signale pregleda v zunanjem pregledovalniku SiWIM eventov. Dve možnosti sta zato, ker v *CF* event-ih ni diagnostike za  detektorje osi, v *ADMP* event-ih pa ni diagnostike o tehtanju.

#### *Photo*

Ko se izbere skupine osi, se v razdelku *Photo* takoj pojavi prva fotografija znotraj te grupe. Primer je na naslednji sliki:

![photo](photo.png)

V imenu razdelka je napisana zaporedna številka vozila, število vseh vozil, timestamp vozila, ID fotografije ter *ORIGINAL*, če oznake slike niso bile spremenjene ali `CHANGED`, če so bile. Na dnu razdelka je izpisano uporabniško ime zadnjega, ki je fotografijo videl ter, če so bile oznake spremenjene, ime uporabnika, ki je zadnji spreminjal oznake.

Slike se lahko izbira s puščico gor — `<Up>` ali dol — `<Down>`.  Lahko pa tudi s klikanjem na drsni trak poleg slike.

#### Nastavljanje oznak

V spodnjem delu razdelka *Photo* so polja s katerimi lahko spreminjamo oznake. Skoraj vsa polja imajo asociirano bližnjico, ki je bila izbrana tako, da minimizira porabljen čas in premikanje prstov na tastaturi.

Takoj, ko se zabeleži sprememba katere izmed oznak, se ta sprememba napiše v datoteko `metadata.hdf5`. S tem je možnost, da bi stran vrgli delo, minimalna.

##### Tip vozila

Z `<Alt>-C` (za **C**hange) se preklaplja med *Bus* in *Truck*. Nekateri tovornjaki, ki jih je AI napačno klasificiral kot avtobus, imajo že nastavljeno to izbirno polje (na osnovi skupin osi)

##### Osi

V polju *Groups* se prikažejo trenutno detektirane skupine osi, npr., 113. Če se izkaže, da je SiWIM napačno detektiral osi, se tukaj popravi v pravilno vrednost. Vnos se konča s pritiskom na tipko `<Enter>`. V polju obstaja tudi "undo", s klasično tipko `<Ctrl>-Z`. 

V polju *Raised* se navede zaporedno številko dvignjene osi. Tipičen primer je, ko šleper dvigne prvo os v trojčku na polpriklopniku. Tedaj bi SiWIM detektiral skupine 112. V tem primeru spremenimo skupine na 113, v polje *Raised* pa se vpiše 3 — dvignjena je tretja os po vrsti.

##### Označevanje napak

V naslednjem razdelku se nastavi potrditvena polja za razne napake.

- **Napačni pas:** Načeloma so med vozili izbrana samo tista, ki jih je SiWIM detektiral na prvem pasu. Če je AI našel vozilo na drugem pasu, se to označi tukaj. Bližnjica je `<Alt>-L` za *Wrong **l**ane*.
- **Napačno vozilo:** Včasih AI detektira drugo vozilo, na primer avtobus, ki vozi blizu kombija. Bližnjica je `<Alt>-V` za *Wrong **v**ehicle*.
- **S pasu:** Včasih se zgodi, da vozilo ne vozi po svojem pasu. Bližnjica je `<Alt>-O`, za ***O**ff lane*.
- **Slika odrezana spredaj:** Če je slika vozila odrezana na sprednjem koncu vozila. Bližnjica je `<Alt>-F` za *Photo trunc. **f**ront*.
- **Slika odrezana zadaj:** Če je slika vozila odrezana na zadnjem koncu vozila. Bližnjica je `<Alt>-F` za *Photo trunc. **b**ack*.
- **Vozilo razpolovljeno:** Če je medosna razdalja v kakšnem vozilu daljša od najdaljše v klasifikacijski tabeli, SiWIM razpolovi vozilo med tema osema v dve vozili. Bližnjica je `<Alt>-H` za *Veh. **h**alved*.
- **Presluh:** Včasih pride do presluha z enega pasu na drugega in vozilo se pojavi na obeh pasovih. Bližnjica je `<Alt>-R` za *C**r**osstalk*.
- Zadnjo možnost se uporabi, ko ni dovolj informacij, da bi sploh pregledal sliko in jo označil (ali pa ne). Tedaj se uporabi **Ne morem označiti**. Bližnjica je `<Alt>-N` za *Ca**n**not label*.