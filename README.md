## What is this thing?

This is small pile of code, using FPDF that will generate 11x17 PDFs for 
the stage signs we use at Hubba. It is a pain in the ass to type in 30 
people's names into Illustrator or Indesign and create PDFs by hand. 
With a fair amount of math, this does that automatically.

Features

- Given any font, maximize the person's name on the sheet in Landscape mode
- Deals with multiple-word stage names well
- Centers it all on the stage
- Takes one or more names in names.txt and cranks out as many PDFs as you want.
- Extensive debugging for margins and such
- No BS page generator

## Setup

This area uses virtualenv to manage packages.

If you change or add packages, remember to update the
`requirements.txt` file for future developers!

Do that with:

`pip3 freeze > requirements.txt`

Please check before overwriting!

# Fresh install

This code requires python3.7 or better.

On a new checkout, you'll need to pull and rebuild the virtual environment. Do that like so:

```
# set as needed
PYTHON=python3

rm -rf .venv
$PYTHON -m venv .venv
source .venv/bin/activate

# optional, and shuts up warnings
pip3 install --upgrade pip 

# installs all dependencies
pip3 install -r requirements.txt
```

# TTFs, copyright, and embedding. 

Apparently you can restrict if a font can be embedded or not. The fonts that we use for Hubba are open sourced
but oddly, were locked. ttfpatch will deal with this idiotic restriction.

If you have the same problem, To patch a ttf, this command will do an inplace update of the font. 2 is restricted, 4 is not.

```
ttfpatch/ttfpatch Fontdinerdotcom-unlocked.ttf 4
```

