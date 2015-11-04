# bucket_mill
A bucket milling (as opposed to bucket filling) algorithm for CNC milling rough cuts for cutting only a little bit at a time.

I would like to point out that this code might not be the most effective when compared to a number of commercial tools and it might not be as good as some free tools our there. It is not meant to be. This is merely a fun project for me.

I first came up with the idea for this project when I saw that the tool path that one free tool that I had was cutting deep without any consideration for how deep I could cut at a time. I have a ShapeOko2 CNC mill and the a weak dremel tool for the cutting part. It can't cut very deep at a time without missing steps.

The scanline option for this is simply not ready for use.

I have edge1, edge2, edge3, edge4 options that will get good results now.

These algorithms might not take advantage of the idea that the dremel bit cuts more than 1 mm at a time. After it does, it should be a bit faster.

The measurements are assumed to be in milimeters.
