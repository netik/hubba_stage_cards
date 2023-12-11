#!.venv/bin/python

import os 
from fpdf import FPDF
from datetime import datetime

# This python program takes in a list of names (as names.txt) and creates a pdf
# file for each name for use in Hubba Hubba stage cards

# --- constants ---
IN_TO_MM = 25.4

# A point equals 1/72 of an inch, that is to say about 0.35 mm (an inch being
# 2.54 cm). This is a very common unit in typography; font sizes are expressed
# in this unit. The default value is mm.
PT_TO_MM = 0.352778

# --- config starts here ---
# 11x17 paper in landscape
HEIGHT = 11 * IN_TO_MM
WIDTH = 17 * IN_TO_MM

LEADING = 5  # mm - extra spacing between lines
DEBUG = True  # set to True to see lines and bounding boxes

# when trying to find the next font size that fits, what do we step by?
FONT_STEP = 2

# since most of these are names, a good starting point is about 100pt
FONT_MIN = 100
FONT_MAX = 800

# Check whether the specified path exists or not

# current date and time
now = datetime.now()
OUTDIR = now.strftime("%Y_%m_%d")

if not os.path.exists(OUTDIR):
    os.makedirs(OUTDIR)

class PDF(FPDF):
    '''
    uses the FPDF class to make Hubba hubba stage signs
    '''
    MYFONT = 'diner'

    def get_font_height(self, font_size, txt):
        ''' create a fake page (gross) and use it to calculate font metrics '''
        temp_pdf = PDF(orientation='L', unit='mm',
                       format=(HEIGHT, WIDTH))
        temp_pdf.add_font(
            family='diner', style='', fname='./Fontdinerdotcom-unlocked.ttf', uni=True)
        temp_pdf.add_page()
        temp_pdf.set_xy(0, 0)
        temp_pdf.set_font(self.MYFONT, '', font_size)

        # alignment probably doesn't matter here.
        temp_pdf.multi_cell(w=self.w-1.0, h=(font_size*PT_TO_MM) +
                            LEADING, align='C', txt=txt, border=1)
        return temp_pdf.get_y()

    def get_multi_cell_height(self, w, h, txt, border=0, align='J'):
        '''
        Calculate MultiCell with automatic or explicit line breaks height
        $border is un-used, but I kept it in the parameters to keep the call
        to this function consistent with MultiCell()
        '''

        if border < 0:
            border = 0

        cw = self.current_font['cw']

        if w == 0:
            w = self.w - self.r_margin - self.x

        wmax = (w-2*self.c_margin) * 1000 / self.font_size
        s = txt.replace("\r", '')

        nb = len(s)
        if nb > 0 and s[nb-1] == "\n":
            nb = nb - 1

        sep = -1
        i = 0
        j = 0
        l = 0
        ns = 0
        height = 0

        while i < nb:
            # Get next character
            c = s[i]

            if c == "\n":
                # Explicit line break
                if (self.ws > 0):
                    self.ws = 0
                    self._out('0 Tw')

                # Increase Height
                height += h
                i = i + 1
                sep = -1
                j = i
                l = 0
                ns = 0
                continue

            if c == ' ':
                sep = i
                ls = l
                ns = ns + 1

            l += cw[ord(c)]

            if l > wmax:
                # Automatic line break
                if sep == -1:
                    if i == j:
                        i = i + 1

                    if self.ws > 0:
                        self.ws = 0
                        self._out('0 Tw')

                    # Increase Height
                    height += h
                else:
                    if align == 'J':
                        if ns > 1:
                            self.ws = (wmax-ls) / 1000*self.font_size / (ns-1)
                        else:
                            self.ws = 0

                        self._out("%.3F Tw" % self.ws*self.k)

                    # Increase Height
                    height += h
                    i = sep+1

                sep = -1
                j = i
                l = 0
                ns = 0
            else:
                i = i + 1

        # Last chunk
        if self.ws > 0:
            self.ws = 0
            self._out('0 Tw')

        # Increase Height
        height += h

        return height

    def get_longest_word(self, txt):
        ''' given a multi-line text, find the longest word '''
        words = txt.split()
        longest = max(words, key=len)
        return longest

    def get_max_font_size(self, text, max_width, step=FONT_STEP, font_min=FONT_MIN, font_max=FONT_MAX):
        ''' find the largest possible font that can fill the page, returning font metrics '''
        if max_width < 0:
            max_width = 1.0

        if step < 0:
            step = 1.0

        if font_min < 0:
            font_min = 1.0

        font_size = font_min
        text_width = 1.0
        text_height = 1.0

        while True:
            self.set_font_size(font_size)
            # get_string_width is problemmatic - if you feed it 'major
            # subtle-tease' it puts all of that together and tries to fthe
            # length as one line ignoring word breaks. So, we use the longest
            # word instead.

            # strategy 1, is we have a single line of text. 
            if (len(text.split()) < 3):
                text_width = self.get_string_width(text)
            else:
                # stragegy 2, we have multiple lines of text, so use the widest word
                text_width = self.get_string_width(self.get_longest_word(text))
                
            # HACK: maybe this is a crap idea too? Are there better font-height metrics?
            font_height = self.get_font_height(font_size, self.get_longest_word(text))
            text_height = self.get_multi_cell_height(
                self.w, font_height + LEADING, text, border=0, align='C')

            print(f'\nTrying {font_size:.2f} px {font_size * PT_TO_MM:.2f} mm')
            print(f'font_size / font_height: {font_height:.2f}')
            print(f'text width: {text_width:.2f}, text height {text_height:.2f}')

            if text_width > (max_width - self.l_margin - self.r_margin):
                print(
                    f'LIMIT: font width {text_width:.2f} mm maxed out at {max_width:.2f}')
                font_size = font_size - step
                break

            # for some reason this doens't work well and the bottom margin is always wrong.
            if text_height > (self.h - self.t_margin - self.t_margin):
                print(
                    f'LIMIT:  overall text height {text_height:.2f} exceeds {self.h - self.t_margin - self.t_margin:.2f}mm')
                font_size = font_size - step

                break

            if font_size >= font_max:
                print(f'LIMIT: font size maxed out at {font_size:.2f}')
                break

            font_size += step  # larger step is faster, smaller step is more accurate

        # this is the biggest you can get without going over
        self.set_font_size(font_size)

        return {
            'font_size': font_size,
            'font_height': font_height,
            'text_width': text_width,
            'text_height': text_height
        }

    def make_labelled_line(self, y1, r, g, b, label):
        ''' draw a dashed line with a label in the current font and color '''
        font_size = 30
        self.set_xy(0, y1 - (font_size * PT_TO_MM))
        self.set_line_width(0.2)
        self.set_draw_color(r, g, b)
        self.set_text_color(r, g, b)
        self.set_font(self.MYFONT, '', font_size)
        self.cell(self.w, h=font_size * PT_TO_MM,
                  align='L', txt=label, border=0, ln=0)
        self.dashed_line(0, y1, self.w, y1, 3, 2)

    def add_name(self, txt):
        ''' add one large name to the page '''
        # setup font
        self.set_xy(0.0, 0.0)
        self.set_font(self.MYFONT, '', 100)
        self.set_text_color(0, 0, 0)

        metrics = self.get_max_font_size(txt, self.w)

        # debug lines
        if DEBUG:
            self.make_labelled_line(self.t_margin, 255, 0, 0, 'MARGIN')

        # there's a little fudge factor here because the text is a little oddly shaped
        # we probably shouldn't subtract t-margin.
        y_offset = ((self.h - self.t_margin) / 2) - (metrics['text_height'] / 2)

        if DEBUG:
            print (f'   page height: {self.h:.2f}')
            print (f'   t_margin:    {self.t_margin:.2f}')
            print (f'   text_height: {metrics["text_height"]:.2f}')
            print (f'   font_height: {metrics["font_height"]:.2f}')   
            print(f'   y_offset: {y_offset}')  
            self.make_labelled_line(y_offset, 0, 255, 0, 'YOFFSET')

        self.set_xy(0, y_offset)
        self.set_fill_color(0, 0, 0)
        self.set_text_color(0, 0, 0)
        self.set_font(self.MYFONT, '', metrics['font_size'])

        # Finally, draw our text!
        if DEBUG:
            self.set_draw_color(255, 0, 255)
            self.multi_cell(w=self.w,
                            h=metrics['font_height']+LEADING,
                            align='C',
                            txt=txt,
                            border=1)
        else:
            self.multi_cell(w=self.w,
                            h=metrics['font_height']+LEADING,
                            align='C',
                            txt=txt,
                            border=0)


def main():
    ''' program start '''
    namefile = open('names.txt', 'r', encoding='utf-8')

    for line in namefile:
        if len(line.strip()) < 2:
            print("skipping blank.")
            continue
        
        # full syntax
        pdf = PDF(orientation='L', unit='mm', format=(HEIGHT, WIDTH))

        # sometimes if we are close to the page limits which casues auto page break
        # to fire and create new pages. turn this off.
        pdf.set_auto_page_break(False)
        pdf.add_font(family='diner', style='',
                     fname='./Fontdinerdotcom-unlocked.ttf', uni=True)
        pdf.add_page()

        # draw the margins if we can
        if DEBUG:
            print('\n')
            print(f'page WIDTH: {pdf.w:.2f} page height: {pdf.h:.2f}')
            print(f'marginL: {pdf.l_margin:.2f} marginR: {pdf.r_margin:.2f}')
            print(f'marginT: {pdf.t_margin:.2f} marginB: {pdf.b_margin:.2f}')

            # draw that.
            pdf.set_draw_color(255, 255, 0)
            pdf.rect(0, 0, pdf.w, pdf.h, 'D')
            pdf.set_draw_color(255, 0, 0)

            # note that we are going to use t_margin twice, because b_margin is
            # always zero when autopagebreak is off
            pdf.rect(pdf.l_margin,  # x
                     pdf.t_margin,  # y
                     pdf.w - pdf.r_margin - pdf.l_margin,  # w
                     pdf.h - pdf.t_margin - pdf.t_margin,  # h
                     'D')

        print(f'\n{line.strip()}\n')

        # place the name
        # if there are < 3 tokes, we don't break the line
        if len(line.split()) < 3:
            pdf.add_name(line.strip())
        else:
            pdf.add_name(line.strip().replace(' ', '\n'))

        outputfn = OUTDIR + '/' + line.strip().replace(' ', '_') + '.pdf'
        pdf.output(outputfn, 'F')

main()
