# Vacuula installer

<img src="src/assets/logo.svg" alt="Vacuula logo" width="150" align="left" />

Welcome to the Vacuula installer, a cross-platform application that turns your artificially dumbed-down robot into an immortal\* dust-sucker — as easy as ~~possible~~ we could make it!<br /><sub>\* Still can get physically damaged by wooden stakes, among other things.</sub>

<br />

[![Latest release](https://img.shields.io/github/v/release/vacuula/installer?style=for-the-badge&label=download&color=brightgreen)](https://github.com/vacuula/installer/releases/latest) [![Discord](https://img.shields.io/badge/chat-Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.gg/PAgwhWvyD8/)

<br clear="left" />

The installer supports all generation 3 and 4 Neato robots (D3 → D10), and should work on Linux distros, Windows (7+) and *__partly__* on mac\* (\*gen3 robots work, gen4 do not). *Botvac Connected is currently not supported.*

<details><summary>Don't have a Neato robot vacuum, but stumbled here from somewhere?</summary>
  
Let's just say Neato robots are *really* cheap on the second hand market now for some reason, this project returns their value *(and depending on how much you value your integrity and ownership of what you buy, surpasses it)*.

</details>

> [!IMPORTANT]
> __Before you can let Vacuula *bite* your robot vacuum(s), you must install the vacuula-server that replaces the closed Neato servers.__ This arrangement puts you in control of your own data and lifetime of the robot(s). If you haven't set up a server yet, learn about it (and download) at [github.com/vacuula/vacuula](https://github.com/vacuula/)!

<div>
  
The installer is as batteries-included as we could make it, but of course we can't predict all states the robots are in. Particularly if your robot is in the "$`\color{#A020F0}{\textsf{r}}\color{#802DF6}{\textsf{a}}\color{#6037FA}{\textsf{i}}\color{#403FFD}{\textsf{n}}\color{#2044FE}{\textsf{b}}\color{#0047FF}{\textsf{o}}\color{#3C3EE6}{\textsf{w}}\ \color{#7839D2}{\textsf{m}}\color{#AA37BE}{\textsf{o}}\color{#D23AAF}{\textsf{d}}\color{#FF3FA4}{\textsf{e}}`$" and refuses to start fully, there can be many different causes which vary in how easy they are to fix (but most can!). To get help use the [discord server](https://discord.gg/PAgwhWvyD8/) or the discussions tab here.

</div>


The installer __collects no data, only modifies your vacuum for the sole reason of allowing it to be controlled by your own server__. Generation 3 robots (after being bitten by vacuula) *currently* use nip.io to help connect to your server, this is a limitation of the models we haven't managed to work around cleanly yet.

## Download from the latest release page!

Do not download from anywhere else, this is an app that modifies your robot, which is connected to your network and only the version(s) found here are based on this open-source code. Other locations might have added nefarious code which you probably really don't want.

## Help us translate the app!

Are you missing a language? You can help!

You can translate either from [en.html](https://github.com/vacuula/installer/blob/main/en-v14.html) or [sv.html](https://github.com/vacuula/installer/blob/main/sv-v14.html) (open in browser or word/writer..). If you open in browser save the file often as it does not save for you (keep the .html).

When you are done send the file to preferably Rinkana but any of the devs is fine! Discord, download link whatever you fancy! Make sure to convey the name you want to be credited by!

Do not translate literally, make it sound natural; as you would say in person speaking that language!

**Do not use AI for the translation**, that we could have done ourselves - do a language you are fluent in so you can detect what sounds awkward!

If you want to fully integrate the language yourself, there are instructions in the DEV-README on how to translate without a dev being the middle man!

## Disclaimer

We are not affiliated with Neato.

We offer no guarantee, __you try to revive your robot on your own risk__ - we are however eager to help! Jump in discord or the discussions here!


## Frequently asked questions

- Robot not detected on Linux and you have a gen3 device? You need to add yourself to the group dialout `sudo usermod -aG dialout <username>` and reboot your computer
- READ THE DISCLAIMER, it has important information!
- Yes *bitten* is used as a synonym to *installed* (or hacked/freed)

## I want to help with the development! (yes there are things to improve)

Take a look at DEV-README.md!

The installer is written in python using Qt6 (pyside6)

## By whom, why?

This app has been developed from a passion to fight arbitrary decrepitation, an idea that maybe it is not how it should be that millions of robot vacuums get turned into ewaste-ish overnight by a whim of business.

Also it has been fun to try to do a clean UI that still handles the rather extensive quirks and limitations of the different models and cracking procedures.

Special thanks to:
- Philip for the Vacuula project itself and for helping to add handling of quirks of the vacuum cleaners I don't have at home, getting it over the finish line.
- nescio007, BK, "*Your royal highness* Sarcast *the 3rd, duke of Holland*", Leander and everyone else in core team who have provided methods to root the different Neatos and/or helped test the installer
- Fjalar for getting it to modern build tooling, so we did not have to play with venvs forever.
- Me myself, Rinkana, for most of the app and UX direction. I take no credit for the amazing exploits that enable this (and the entire Vacuula project).

Translations:
- English: Rinkana, Philip, BK
- Swedish: Rinkana, Philip
- Dutch: Leander, "*Your royal highness* Sarcast *the 3rd, duke of Holland*"
- Portuguese: BK 
- Deutsch: Christian Kütbach

