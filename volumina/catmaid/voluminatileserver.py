###############################################################################
#   volumina: volume slicing and editing library
#
#       Copyright (C) 2011-2014, the ilastik developers
#                                <team@ilastik.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the Lesser GNU General Public License
# as published by the Free Software Foundation; either version 2.1
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# See the files LICENSE.lgpl2 and LICENSE.lgpl3 for full text of the
# GNU Lesser General Public License version 2.1 and 3 respectively.
# This information is also available on the ilastik web site at:
#		   http://ilastik.org/license/
###############################################################################
#!/usr/bin/python

# The VoluminaTileServer is a proof-of-concept demonstrating how to
# serve tiles to be consumed and displayed by CATMAID

# Requirements:
# sudo pip install tornado

import tornado.ioloop
import tornado.web

import Image
import io 
import numpy as np

# This handler serves tiles from e.g. volumina
class TileHandler(tornado.web.RequestHandler):
	
	def initialize(self, database):
		self.database = database
		
	def get(self):
		print("the get request", self.request)
		
		# parse the arguments
		#z=self.get_argument('z')
        # the usable parameters posted are:
        # x, y, dx : tileWidth, dy : tileHeight,
        # scale : scale, // defined as 1/2**zoomlevel
        # z : z
        # everything in bitmap pixel coordinates
		
		# create an example PNG
		w,h=256,256
		img = np.empty((w,h),np.uint32)
		img.shape=h,w
		img[0,0]=0x800000FF
		img[:100,:100]=0xFFFF0000
		pilImage = Image.frombuffer('RGBA',(w,h),img,'raw','RGBA',0,1)
		imgbuff = io.StringIO() 
		pilImage.save(imgbuff, format='PNG') 
		imgbuff.seek(0)
		self.set_header('Content-Type', 'image/png') 
		self.write(imgbuff.read()) 
		imgbuff.close()
		self.flush()
        
	def post(self):
		print("the post request", self.request)
		self.write("hello post")

# This handler manages POST request from the canvas label painting
class LabelUploader(tornado.web.RequestHandler):
	
	def post(self):
		datauri = self.get_argument('data')[0]
		output = open('output.png', 'wb')
		output.write(datauri.decode('base64'))
		output.close()
		self.write("success")
	

VoluminaTileServer = tornado.web.Application([
    (r"/", TileHandler, dict(database="123")),
    (r"/labelupload", LabelUploader),
])

if __name__ == "__main__":
    VoluminaTileServer.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
