from reportlab.platypus import Table, Image
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import ttfonts, pdfmetrics

class pdf_creator:

    def __init__(self, start_height: int, start_x: int, path: str, verbose: bool):
        self.file = Canvas(path)
        self.start_height = start_height
        self.height = start_height
        self.start_x = start_x
        self.verbose = verbose
        pdfmetrics.registerFont(ttfonts.TTFont("MesloLGS NF Bold", "MesloLGS NF Bold.ttf"))
        pdfmetrics.registerFont(ttfonts.TTFont("MesloLGS NF", "MesloLGS NF Regular.ttf"))
        self.set_leading(16)

    def text(self, string: str, x: int, y: int):
        self.file.drawString(x, y, string)

    def text(self, string: str, x: int):
        self.handle_height_change()
        self.file.drawString(x, self.height, string)

    def show_text(self, string: str):
        self.text(string, self.start_x)

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

        #table_width = self._calculated_width(data)


        #while self.leading > 4 and table_width < 200:
        #    self.leading -= 1

        # TODO handle new page
        #if self.height - table_height < 50:
        #    print("Found table height too large: " + str(table_height))
        #    print("Current height: " + str(self.height))

        end_y = self.height - table._height
        
        if x < 0:
            x = self.start_x
        
        if self.verbose:
            print("Actual table dims: ({}, {})".format(table._height, table._width))
        
        table.drawOn(self.file, x, end_y)


    def _calculate_height(self, data: list):
        table_height = 0
        for row in data:
            row_lines = 1
            for cell_value in row:
                n_lines = cell_value.count("\n") + 1
                if n_lines > row_lines:
                    row_height = n_lines

            table_height += (row_lines * self.leading)
            table_height += self.leading * 1.5

        return table_height


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

    def image(self, path: str, x: int, y: int):
        """
        :param path: to image
        :param x: image-cordinate
        :param y: image-cordinate
        """
        image = Image(path)
        image.drawOn(self.file, x, y)

    def add_page(self):
        self.file.showPage()
        self.height = self.start_height
        self.file.setFont(self.font, self.size)

    def save(self):
        self.file.save()

