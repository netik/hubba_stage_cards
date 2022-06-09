## Setup

This area uses virtualenv to manage packages.

If you change or add packages, remember to update the
`requirements.txt` file for future developers!

Do that with:

`pip3 freeze > requirements.txt`

Please note: If you are developing locally on MacOS, there are a large
number of packages which are not available on CentOS. The existing
requirements.txt has been heavily modified to work on CentOS. If you
overwrite the entire file with new versions, you may break
production/staging builds.

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

# Fucking ttfs

Apparently you can restrict if a font can be embedded or not. ttfpatch
will deal with this idiotic restriction.

To patch a ttf, this command will do an inplace update of the font. 2 is restricted, 4 is not.

```
ttfpatch/ttfpatch Fontdinerdotcom-unlocked.ttf 4
```

