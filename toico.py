from PIL import Image
img = Image.open("cover.png")
img.save("cover.ico", format="ICO", sizes=[(256,256), (128,128), (64,64), (32,32), (16,16)])