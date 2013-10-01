*****************
Pixel pipeline
*****************

.. _fig-pixelpipeline:
.. figure:: img/pixelpipeline.png
   :width: 640px
   :alt: pixel pipeline class interaction diagram

   Pixel pipeline architecture.

The pixel rendering pipeline or short *pixel pipeline* renders 2d
bitmap images from several multidimensional scalar data sources. It
can produces several kinds of images, amongst others: grayscale, rgba,
alpha-modulated, and colortable images. Each image type needs up to
four scalar data sources as input, for example one source for each
channel (red, green, blue, and alpha) in case of a rgba image.

Furthermore, these images can be combined into a stack using alpha
blending with an image of the rendered stack as output. A schematic of
the pixel pipeline architecture is shown in the 
:ref:`above Figure <fig-pixelpipeline>`. The visual properties of one image are contained
in a *layer* object and a ordered stack of layers is organized in a
*LayerStack*. They serve as a rendering blueprint used in *image
pumps*. A image pump takes the blueprint together with the data
sources and renders a 2d image. Internally, a image pump consists of
subcomponents that take care of slicing through the correct axes of
the multidimensional data sources and the blending of several layers
into a stack image. Furthermore, several image pumps can be connected
to the same layer stack and data sources allowing to render different
slice views simultaneously.

The pixel pipeline is a lazy data flow processing pipeline, that is,
subregions of images can be requested from the pipeline and only the
calculations necessary to complete the request are actually performed.  

