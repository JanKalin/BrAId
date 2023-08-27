# Kratko poročilo o računu prečnega položaja

Najprej malo ozadja. Prejšnji teden smo imeli debate okoli določanja prečnega položaja, kjer smo se spomnili na Evin članek o korekcijah faktorja (članek prilagam) in debatirali o možnosti določanja prečnega položaja iz odzivov.

Zato sem posvetil par dni za reprodukcijo rezultatov iz članka ter možnosti določanja prečnega položaja.

## Postopek

Na kratko gre postopek takole:

- Na prečni raznos prilagajaš Gaussovo krivuljo plus linearno funkcijo (ki poskrbi za offset in "nagnjenost" odziva). S tem dobiš štiri parametre $\beta$, pri čimer sta $\beta_3$ sredina Gaussove krivulje in $\beta_4$ standardna deviacija - širina.

- Za vsak dogodek izračunaš korekcijski faktor $k_j$ za posamezni kanal $j$ tako, da se korigiran prečni raznos ujema s prilagojeno funkcijo za tisti dogodek.
- Po koncu se korekcijske faktorje povpreči in proglasi za "MP faktorje" (MPf).

Poleg tega so bili poizkusno še izpuščeni posamezni senzorji. Senzor 8 je namreč bil montiran preko razpoke in je imel precej večji odziv. Z izpuščenim tem senzorjem sta se krivulji za en in drug pas bolje ujemali, čeprav je to morda bilo bolj navidezno (bomo kasneje videli zakaj).

V članku se je za vozila stehtana s tako popravljenimi odzivi natančnost GVW in skupin izboljšala iz C(15) na B(10), posameznih osi pa B(10) na B+(7).

## Reproduciranje članka

Za analizo sem vzel iste podatke, kot v članku — AC_Sentvid_2012 iz avgusta 2013 — iz katerih sem izpustil vse MP dogodke in vozila lažja od 3.5t. Število podatkov, 26074,  se ni točno ujemalo s citiranim v članku, 30567, ampak je dovolj blizu. Žal nimam več podatkov, ki sem jih dal Evi.

Za prilagajanje in analizo je bil uporabljen Python s knjižnicami Pandas, SciPy in SiWIM-Pi.

Pri računih sem predpostavil, da je razdalja med senzorji kar 1m, čeprav je v članku navedena razdalja 1.05m. Pri zadevah, ki se bodo tukaj dogajale, 5% ne spremeni ničesar.

### Račun z vsemi senzorji

![1-all-factors-mean-individual](D:\siwim\siwim-pi-examples\transverse_position\report\1-all-factors-mean-individual.png)

Na sliki 1 je rezultat prej opisanega postopka. Slika se zelo lepo ujema s sliko 4 iz članka. Oznake na sliki pomenijo:

- **All channels** da so bili uporabljeni vsi kanali
- $\bar{k_j}$ pomeni, da so MPf-ji izračunani na osnovi povprečnih faktorjev posameznih dogodkov. Možnosti sta še $\tilde{k_j}$, kjer je uporabljena mediana namesto povprečja, ter $\bar{\beta_i}$, kjer se vzame povprečje prilagojenih parametrov, izračuna vrednosti funkcije pri posameznih senzorjih in to uporabi za generiranje MPfj-ev.
- **per lane MPs**, pomeni, da se uporabijo MPf-ji za vsak pas posebej. Druga možnost je, da se uporabi povprečje faktorjev za oba pasova.
- $\beta_3$ in $\beta_4$ sta povprečji parametrov prilagojenih funkcij
- $\beta_3'$ in $\beta_4'$ pa sta parametra prilagojenih funkcij, ki jih prilagajamo na že korigirane raznose, se pravi, opisujeta oranžno in rdečo krivuljo.

Se pravi, na tej sliki je točno reproduciran postopek iz članka za sliko 4 - uporabljeni so vsi kanali, uporabi se povprečje faktorjev in faktorje za vsak pas posebej. Oranžna krivulja se ujema z modro in rdeča z rdečo.

Na osnovi razlik v širinah krivulj $\beta_4'$ za prvi in drugi pas — 2.18 in 1.48, ki se razlikujeta za 32% — je bi v članku zaključek, da je prilagajanje napačno zaradi napačnega osmega senzorja, češ da predstavlja ne-fizikalno obnašanje mostu, saj bi morala odziva biti približno enake širine. Vendar mislim, da je to napačen zaključek, oziroma, da so predpostavke, ki vodijo v ta zaključek napačne.

V SiWIM je namreč nemogoče upoštevati faktorje za vsak pas posebej, temveč se ima vedno vsak senzor svoj faktor ne glede na pas. Če namesto uporabe faktorjev za vsak pas le-te združimo, dobimo precej drugačno sliko 2:

![2-all-factors-mean-mean](D:\siwim\siwim-pi-examples\transverse_position\report\2-all-factors-mean-mean.png)

Širini krivulj sta sedaj skoraj identični – 1.69 in 1.60 ali razlika 5%. Tukaj je edina težava v negativnem prispevku na prvem kanalu na pasu 1, drugače pa je slika bolj "fizikalna". Negativnega prispevka se rešimo tako, da za račun MPf-jev uporabimo mediano namesto povprečja, kar se vidi na naslednji sliki 3:

![3-all-factors-median-mean](D:\siwim\siwim-pi-examples\transverse_position\report\3-all-factors-median-mean.png)

Širini krivulj se sicer sedaj razlikujeta za 12%, vendar sta si še vedno precej podobni. Podobno sliko  4 dobimo z uporabo povprečnih parametrov:

![4-all-pars-median-mean](D:\siwim\siwim-pi-examples\transverse_position\report\4-all-pars-median-mean.png)

Širini se sicer še vedno razlikujeta za 12%, vendar je to po mojem mnenju v redu. Če si predstavljamo ekstremni situaciji, ko je obremenitev na sredini plošče in na robu plošče: V prvem primeru se bo prečni raznos širil preko cele plošče, podobno, kot na pasu 1 na zgornji sliki. Če pa bi dali obremenitev na rob plošče, bi se (na sliki) levo od obremenitve raznos padal približno tako, kot na pasu 1, le zamaknjen v desno. To se na sliki tudi opazi — poziciji vrhov raznosov na pasu 1 in 2 se razlikujeta za približno 2m, raznos na pasu 2 pa je na senzorju $j+2$ skoraj enak raznosu na pasu 1 na senzorju $j$ (senzorji so okoli 1m narazen). Raznos desno od vrha pa bi se "prezrcalil", oziroma prenesel v večji vzdolžni upogib. S tem pa postane širina raznosa manjša, če je obremenitev bolj proti robu plošče, in dobljeni rezultat po mojem mnenju primeren.

### Račun brez senzorja 8

Skupen problem vseh teh slik pa je, da je razlika vrhov na pasu 1 in 2 precej majhna, 2.3m - 2.0m, kar ne ustreza širini pasov na avtocesti. Morda je to posledica vožnje vozil, morda napačnega izračuna, verjetno pa tudi "pokvarjenega" senzorja 8, ki je bližje vrhu raznosa na pasu 2, vrha raznosa na pasu 1 pa "potegne" proti vrhu na pasu 2. Zato sem ponovil račune brez senzorja 8.

Na sliki 5 je reprodukcija računa iz članka:

![5-noch8-factors-mean-individual](D:\siwim\siwim-pi-examples\transverse_position\report\5-noch8-factors-mean-individual.png)

Razlika širin je zopet majhna, 7%, kar je bilo opaženo tudi v članku, je pa tokrat razdalja med vrhovoma precej večja, 3.5m, kar se zelo lepo ujema z realnostjo. Problem pri izpustitvi kanala 8 pa je ta, da je to zgornja slika edina, ki zgleda OK.

Če uporabimo skupne MPf-je, se slika 6 precej pokvari:

![6-noch8-factors-mean-mean](D:\siwim\siwim-pi-examples\transverse_position\report\6-noch8-factors-mean-mean.png)

Tudi če zanemarimo negativni prispevek prvega senzorja, je korigirana slika za pas 2 čudna z velikim prispevkom na zadnjem senzorju. Tokrat rešitev ni ne uporaba mediane na sliki 7:

![7-noch8-factors-median-mean](D:\siwim\siwim-pi-examples\transverse_position\report\7-noch8-factors-median-mean.png)

ne uporaba parametrov na sliki 8:

![8-noch8-pars-median-mean](D:\siwim\siwim-pi-examples\transverse_position\report\8-noch8-pars-median-mean.png)

Od teh je slika 7 še najbolj "lepa" s podobnima širinama in realističnima razdaljama med vrhovi.

## Račun prečnega položaja

Ko imamo MPf-je, se da na tako korigiranih podatkih se enkrat izvajati prilagajanje funkcije in iz parametra $\beta_3$ razbrati prečni položaj. Računal sem dvakrat:

- z vsemi senzorji, z MPf-ji naračunanimi iz parametrov
- brez senzorja 8, z MPf-ji naračunanimi z mediano iz faktorjev

V obeh primerih sem vzel povprečne MPf-je. V opisih sta "Desno" in "levo" mišljena pri pogledu proti smeri vožnje, se pravi, senzor 1 je na levi.

### Z vsemi senzorji

![9-all_dist](D:\siwim\siwim-pi-examples\transverse_position\report\9-all_dist.png)

Na sliki 9 vidimo histogram prečnih položajev (pozor, skala je logaritemska). Opazno je, da je ogromna večina rezultatov znotraj 5.5m in 8m. Zunaj je vsega skupaj nekaj dogodkov, kar kaze na dobro stabilnost prilagajanja. Če poiščemo slike vozil pri mediani, 6.66m, in pri 6m, dobimo naslednji sliki 10 in 11:

<img src="D:\siwim\siwim-pi-examples\transverse_position\report\all_left.png" alt="all_left" style="zoom: 50%;" />

<img src="D:\siwim\siwim-pi-examples\transverse_position\report\all_med.png" alt="all_med" style="zoom: 50%;" />

Razlika s slike je večja, kot pri prilagajanju, 0.66m, vendar je pravilno ocenil smer premika. Pri iskanju slik vozil pri mediani +0.66m pa se je izkazalo, da je zelo veliko primerov, ko je na pasu 2 ne-detektirano vozilo, ki popači rezultate. Edini, ki sem ga uspel po dolgem iskanju najti je tovornjak 12, težak 13t, ki se je peljal ponoči ob 2h in kjer luči nakazujejo, da je res peljal bolj proti svoji levi črti, na sliki 12.

<img src="D:\siwim\siwim-pi-examples\transverse_position\report\all_right.png" alt="all_right" style="zoom:50%;" />

### Brez senzorja 8

![13-noch8_dist](D:\siwim\siwim-pi-examples\transverse_position\report\13-noch8_dist.png)

Na sliki 13 je porazdelitev brez kanala 8. Prečni položaj je tukaj manjši (bolj levo), ker pokvarjeni senzor ne vleče več porazdelitve in prilagajane funkcije v desno. Zopet je zelo malo napačnih rezultatov prilagajanj. Na slikah 14 in 15 sta zopet vozili pri 0.66m levo od mediane in pri mediani. 

<img src="D:\siwim\siwim-pi-examples\transverse_position\report\noch8_left.png" alt="noch8_left" style="zoom:50%;" />

<img src="D:\siwim\siwim-pi-examples\transverse_position\report\noch8_mid.png" alt="noch8_mid" style="zoom:50%;" />

Pri iskanju vozila 0.66m desno od mediane pa je bilo tokrat lažje. Na sliki 16 je primer takšnega vozila.

<img src="D:\siwim\siwim-pi-examples\transverse_position\report\noch8_right.png" alt="noch8_right" style="zoom:50%;" />

Tudi na teh slikah niso izmerjeni prečni položaji sorazmerni dejanskim položajem, vidnim na slikah, so pa vsaj v isto smer.

## Povzetek

Pokazali smo, da je iz signalov na plošči možno določiti prečni položaj vozila iz prečnega s pomočjo prilagajanja modificirane Gaussove funkcije. Na tem mostu je bilo nekaj večjih oviri za bolj natančno določanje prečnega položaja:

- Sam prečni odziv mostu, ki je precej širok. S tem je prilagajanje funkcije bolj občutljivo na šume in napake v meritvi.
- Napačen odziv senzorja 8. Navkljub kompenzaciji je možno, da to vpliva na prilagajanje funkcije.
- Slaba detekcija vozil na pasu 2. Zaradi tega je po vsej verjetnosti prilagajanje "potegnilo" vrh na pasu 1 v desno, kajti navkljub selekciji vozil brez MP, je bilo očitno, da je veliko vozil v resnici bolj levo, kot je bilo izračunano, ker so nedetektirana vozila na pasu 2 pokvarile rezultat.

Na podobni konstrukciji je verjetno težko zagotoviti dobro ujemanje izračunanega in dejanskega prečnega položaja, tudi v primeru dobre detekcije vozil in delujočih senzorjev, zaradi slabo izrazitih vrhov prečne porazdelitve. 

## Ortotropne plošče

Na ortotropnih ploščah pa je zadeva popolnoma drugačna. Tam je prečni odziv zelo oster, presluha s sosednjega pasu skoraj ni in zelo verjetno bi se dalo določiti prečni položaj na nekaj centimetrov natančno.

Edini podatki z ortotropne plošče, ki jih imam na voljo, so z viadukta Millau. Če je verjeti `site.conf`, so si rebra 55cm vsaksebi narazen. Na slikah 17 in 18 sta prečni porazdelitvi pri skrajnih položajih kalibracijskega vozila na pasu 1, na sliki 19 pa ena izmed dveh voženj na pasu 2

![millau_up](D:\siwim\siwim-pi-examples\transverse_position\report\millau_up.png)

![millau_down](D:\siwim\siwim-pi-examples\transverse_position\report\millau_down.png)

![millau_lane2](D:\siwim\siwim-pi-examples\transverse_position\report\millau_lane2.png)

Zelo očitno je, da se na odzivih vidi ne samo vozilo, ampak vsaka sled posebej. Pri taksnem odzivu bi se lahko prilagajalo vsoto dveh Gaussovih funkcij, katerih vrhova bi bila 2.10m narazen, tako, kot je bilo to narejeno v članku. Tam to ni pomembno spremenilo natančnosti tehtanja, tukaj pa je potencial morda velik.

Očitno je tudi, da presluha z enega pasu na drugega ni dovolj, da bi pri nedetektiranih vozilih na pasu 2 (in sploh na pasu 3) to pomembno vplivalo na izračune prečnega položaja na pasu 1. Tudi zato, ker prehitevajo večinoma lažja vozila in bi bil vpliv presluha še toliko manjši.

Moje mnenje je, da bi bil račun prečnega položaja na taksnem mostu dovolj lahko izvedljiv in precej natančen. Pri kalibracijski kampanji, kot je predvidena (zapora mostu,…) bi se splačalo potruditi tudi za to in morda meriti prečno lokacijo vozila,… Na Trnjavi smo to naredili z nalepljenimi črtami na mostu in s kamero v vozilu.

Seveda pa je treba paziti, da so meritve dobre. Na zadnji sliki je razviden anomalen odziv senzorjev 15 in 16, ki dosežejo plato, preko katerega ne gredo. Na prvi sliki pa je takšen senzor 5. Takšnih reči se je treba izogniti. Sprašujem se, če slučajno niso senzorji bili "zabiti"? Kakorkoli, lepljenje lističev je verjetno dober način, da se izogneš takšnim težavam.