from reportlab.platypus import Table, Image
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import ttfonts, pdfmetrics
from reportlab.lib import utils



class pdf_creator:

    def __init__(self, start_height: int, start_x: int, path: str, footer_text: str, verbose: bool):
        self.file = Canvas(path)
        self.start_height = start_height
        self.height = start_height
        self.start_x = start_x
        self.footer_text = footer_text
        self.verbose = verbose
        self.has_completed_first_page = False
        pdfmetrics.registerFont(ttfonts.TTFont("MesloLGS NF Bold", "MesloLGS NF Bold.ttf"))
        pdfmetrics.registerFont(ttfonts.TTFont("MesloLGS NF", "MesloLGS NF Regular.ttf"))
        self.set_leading(16)


    def text(self, string: str, x: int):
        self.handle_height_change()
        self.file.drawString(x, self.height, string)

    def show_text(self, string: str):
        lines = string.split("\n")
        for line in lines:
            self.text(line, self.start_x)

    def set_font(self, font: str, size: int):
        self.font = font
        self.size = size
        self.file.setFont(font, size)

    def set_leading(self, leading: int):
        self.leading = leading

    def newline(self):
        self.handle_height_change()

    def handle_height_change(self):
        self.height -= self.leading
        if self.height < 50:
            self.add_page()

    def _get_table(self, data: list, extra_style_commands: list):
        style = self._get_table_style(extra_style_commands)
        table = Table(data=data, style=style)
        table.wrapOn(self.file, 0, 0)
        return table

    def show_table(self, data: list, extra_style_commands: list, x: int):
        table = self._get_table(data, extra_style_commands)
        
        while self.leading > 4 and self.height - table._height < 50:
            self.leading -= 0.5
            table = self._get_table(data, extra_style_commands)
            if self.verbose:
                print("Reduced leading to " + str(self.leading) + " to reach table height " + str(table._height))
        
        while self.leading > 4 and table._width > 550:
            self.leading -= 0.5
            table = self._get_table(data, extra_style_commands)
            if self.verbose:
                print("Reduced leading to " + str(self.leading) + " to reach table width " + str(table._width))

        # TODO handle new page
        #if self.height - table_height < 50:
        #    print("Found table height too large: " + str(table_height))
        #    print("Current height: " + str(self.height))

        end_y = self.height - table._height
        
        if x < 0:
            x = self.start_x
        
        if self.verbose:
            print("Table dims: ({}, {})".format(table._height, table._width))
        
        table.drawOn(self.file, x, end_y)
        self.height -= table._height


    def _get_table_style(self, extra_style_commands: list):
        style = [("GRID", (0, 1), (-1, -1), 1, "Black"),
                 #("TEXTCOLOR", (0, 0), (0, -1), "White"),
                 ("TEXTCOLOR", (0, 0), (-1, 0), "White"),
                 ("FONT", (0, 0), (0, -1), "MesloLGS NF Bold", self.leading),
                 ("FONT", (0, 0), (-1, 0), "MesloLGS NF Bold", self.leading),
                 ("FONT", (1, 1), (-1, -1), "MesloLGS NF", self.leading),
                 ("BOX", (0, 0), (-1, -1), 1, "Black"),
                 #("BACKGROUND", (0, 0), (0, -1), "Lightgrey"),
                 ("BACKGROUND", (0, 0), (-1, 0), "Darkslategray")]

        if extra_style_commands == None or len(extra_style_commands) == 0:
            return style
        
        style.extend(extra_style_commands)
        return style

    def _getMultiplier(self):
        if self.leading < 6:
            return 2.4
        elif self.leading < 8:
            return 2.3
        else:
            return 1.8

    def show_image(self, path: str, x: int, width=150, height=None):
        img = utils.ImageReader(path)
        iw, ih = img.getSize()
        aspect = ih / float(iw)
        image_height = width * aspect
        scaled_image = Image(path, width=width, height=image_height)
        self.height -= image_height
        scaled_image.drawOn(self.file, x, self.height)

    def add_header_and_footer(self):
        self.set_font("MesloLGS NF", 9)
        self.set_leading(9)
        self.file.drawString(130, self.start_height + 20, self.footer_text)
        self.file.drawString(130, 20, self.footer_text)
    
    def add_page(self):
        if self.has_completed_first_page:
            self.add_header_and_footer()
        else:
            self.has_completed_first_page = True
        self.file.showPage()
        self.height = self.start_height
        self.file.setFont(self.font, self.size)

    def save(self):
        self.file.save()

