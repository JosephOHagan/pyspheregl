"""
Copyright (c) 2018, John H. Williamson <jhw@dcs.gla.ac.uk>

This module was originally based on code which is:

Copyright (c) 2009, Stefan van der Walt <stefan@sun.ac.za>
  
This module was originally based on code from
  
http://swiftcoder.wordpress.com/2008/12/19/simple-glsl-wrapper-for-pyglet/
  
which is
  
Copyright (c) 2008, Tristam MacDonald
  
Permission is hereby granted, free of charge, to any person or organization
obtaining a copy of the software and accompanying documentation covered by
this license (the "Software") to use, reproduce, display, distribute,
execute, and transmit the Software, and to prepare derivative works of the
Software, and to permit third-parties to whom the Software is furnished to
do so, all subject to the following:
  
The copyright notices in the Software and this entire statement, including
the above license grant, this restriction and the following disclaimer,
must be included in all copies of the Software, in whole or in part, and
all derivative works of the Software, unless such copies or derivative
works are solely in the form of machine-executable object code generated by
a source language processor.
  
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE, TITLE AND NON-INFRINGEMENT. IN NO EVENT
SHALL THE COPYRIGHT HOLDERS OR ANYONE DISTRIBUTING THE SOFTWARE BE LIABLE
FOR ANY DAMAGES OR OTHER LIABILITY, WHETHER IN CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
  
"""

from pyglet.gl import *
from ctypes import *
import contextlib
import numpy as np
import np_vbo
import pyglet.gl as gl

class GLSLError(Exception):
    pass

def if_in_use(f):
    """Decorator: Execute this function if and only if the program is in use.
  
    """
    def execute_if_in_use(self, *args, **kwargs):
        if not self.bound:
            raise GLSLError("Shader is not bound.  Cannot execute assignment.")
  
        f(self, *args, **kwargs)
  
    for attr in ["func_name", "__name__", "__dict__", "__doc__"]:
        setattr(execute_if_in_use, attr, getattr(f, attr))
  
    return execute_if_in_use
  
import os


# remove version lines from input shaders and replace with our own
def version_clean(st):    
    return "\n".join([line.strip() for line in st.splitlines() if not line.startswith('#version')])

def shader_from_file(verts, frags,  geoms=None, path="shaders", version="430 core"):
    """Load vertex and fragment shaders from a list of files, and return the compiled shader"""
    v_shaders = []
    v_shaders.append("#version "+version+"\n")
    
    print "\nCompiling shader:\t",
    for vert in verts:
        
        with open(os.path.join(path,vert)) as v:
                print os.path.basename(vert),
                v_shaders.append(version_clean(v.read()))
                
    f_shaders = []
    f_shaders.append("#version "+version+"\n")
    for frag in frags:        
        with open(os.path.join(path,frag)) as f:
                print os.path.basename(frag), 
                f_shaders.append(version_clean(f.read()))
                
    g_shaders = []
    if geoms is not None and len(geoms)>0:
        g_shaders.append("#version "+version+"\n")
        for geom in geoms:
            with open(os.path.join(path,geom)) as f:
                    print os.path.basename(geom),
                    g_shaders.append(version_clean(f.read()))
         
    _shader = Shader(vert=v_shaders, frag=f_shaders, geom=g_shaders)
    
    return _shader

class Shader:
    # vert, frag and geom take arrays of source strings
    # the arrays will be concattenated into one string by OpenGL
    def __init__(self, vert = [], frag = [], geom = []):
        # create the program handle
        self.handle = glCreateProgram()
        # we are not linked yet
        self.linked = False
        
        self.srcs = vert+frag+geom
        # create the vertex shader
        self.createShader(vert, GL_VERTEX_SHADER)
        # create the fragment shader
        self.createShader(frag, GL_FRAGMENT_SHADER)
        # the geometry shader will be the same, once pyglet supports the extension
        self.createShader(geom, GL_GEOMETRY_SHADER_EXT)
        self.uniforms = {}
        self.attribs = {}
        self.bound = False
        # attempt to link the program
        self.link()

    def createShader(self, strings, type):
        count = len(strings)
        # if we have no source code, ignore this shader
        if count < 1:
            return

        # create the shader handle
        shader = glCreateShader(type)

        # convert the source strings into a ctypes pointer-to-char array, and upload them
        # this is deep, dark, dangerous black magick - don't try stuff like this at home!
        src = (c_char_p * count)(*strings)
        glShaderSource(shader, count, cast(pointer(src), POINTER(POINTER(c_char))), None)

        # compile the shader
        glCompileShader(shader)

        status = c_int(0)        
        # retrieve the compile status
        glGetShaderiv(shader, GL_COMPILE_STATUS, byref(status))
        temp = c_int(0)
        glGetShaderiv(shader, GL_INFO_LOG_LENGTH, byref(temp))
        # create a buffer for the log
        buffer = create_string_buffer(temp.value)
        # retrieve the log text
        glGetShaderInfoLog(shader, temp, None, buffer)

        if len(buffer.value)>5:   
            print(buffer.value)
        
        if not status:
            
            raise GLSLError("Failed to compile shader")
        else:
            # all is well, so attach the shader to the program
            glAttachShader(self.handle, shader);            
        
           
            
            
    
        

    def link(self):
        # link the program
        glLinkProgram(self.handle)

        status = c_int(0)
        # retrieve the link status
        glGetProgramiv(self.handle, GL_LINK_STATUS, byref(status))
        temp = c_int(0)
        # create a buffer for the log
        glGetProgramiv(self.handle, GL_INFO_LOG_LENGTH, byref(temp))
        buffer = create_string_buffer(temp.value)        
        glGetProgramInfoLog(self.handle, temp, None, buffer)        
        
        if len(buffer.value)>5:   
            print(buffer.value)
        
        if not status:            
            raise GLSLError("Failed to link shader")
        else:
            # all is well, so we are linked
            glGetProgramiv(self.handle, GL_INFO_LOG_LENGTH, byref(temp))            
            self.linked = True

        AUL = GLint()
        glGetProgramiv(self.handle, GL_ACTIVE_UNIFORM_MAX_LENGTH,
                          byref(AUL))
        self._ACTIVE_UNIFORM_MAX_LENGTH = AUL.value
        self._update_uniform_types()

    def bind(self):
        # bind the program
        self.bound = True
        glUseProgram(self.handle)

    def unbind(self):
        # unbind whatever program is currently bound - not necessarily this program,
        # so this should probably be a class method instead
        glUseProgram(0)
        self.bound=False

        
    def get_uniform(self, name):
        # cache uniform locations
        if name not in self.uniforms:
            self.uniforms[name] = glGetUniformLocation(self.handle, name)
        return self.uniforms[name]
        
    # upload a floating point uniform
    # this program must be currently bound
    def uniformf(self, name, *vals):
            
        # check there are 1-4 values
        if len(vals) in range(1, 5):
            # select the correct function
            { 1 : glUniform1f,
                2 : glUniform2f,
                3 : glUniform3f,
                4 : glUniform4f
                # retrieve the uniform location, and set
            }[len(vals)](self.get_uniform(name), *vals)
            
    def __enter__(self):
        self.bind()
        return self
        
    def __exit__(self, exc_type, exc_value, traceback):
        self.unbind()
    
    # upload an integer uniform
    # this program must be currently bound
    def uniformi(self, name, *vals):
        # check there are 1-4 values
        if len(vals) in range(1, 5):
            # select the correct function
            { 1 : glUniform1i,
                2 : glUniform2i,
                3 : glUniform3i,
                4 : glUniform4i
                # retrieve the uniform location, and set
            }[len(vals)](self.get_uniform(name), *vals)

    # upload a uniform matrix
    # works with matrices stored as lists,
    # as well as euclid matrices
    def uniform_matrixf(self, name, mat):
        # obtian the uniform location
        loc = self.get_uniform(name)
        # uplaod the 4x4 floating point matrix
        glUniformMatrix4fv(loc, 1, False, (c_float * 16)(*mat))

    def uniform_mat4(self, name, mat):
        loc = self.get_uniform(name)
        glUniformMatrix4fv(loc, 1, False, mat.astype(np.float32).ctypes.data_as(POINTER(c_float)))

    def uniform_mat3(self, name, mat):
        loc = self.get_uniform(name)
        glUniformMatrix3fv(loc, 1, False, mat.astype(np.float32).ctypes.data_as(POINTER(c_float)))

    # this program must be currently bound
    # set the vertex attribute to a *constant* value 
    # disregarding its array value
    def attribi(self, id, *vals):
        # check there are 1-4 values
        if len(vals) in range(1, 5):
            # select the correct function
            { 1 : glVertexAttrib1i,
                2 : glVertexAttrib2i,
                3 : glVertexAttrib3i,
                4 : glVertexAttrib4i
                # retrieve the uniform location, and set
            }[len(vals)](id, *vals)

    # this program must be currently bound
    # set the vertex attribute to a *constant* value 
    # disregarding its array value
    def attribf(self, id, vals):        
        # check there are 1-4 values
        if len(vals) in range(1, 5):
            # select the correct function
            { 1 : glVertexAttrib1f,
                2 : glVertexAttrib2f,
                3 : glVertexAttrib3f,
                4 : glVertexAttrib4f
                # retrieve the uniform location, and set
            }[len(vals)](id, *vals)


    def attribute_location(self, name):
        if name not in self.attribs:
            self.attribs[name] = glGetAttribLocation(self.handle, name)
        
        return self.attribs[name]
        

    def draw(self, ibo, vao, textures={}, vars={}, attribs={}, primitives=GL_QUADS, n_prims=0):
        self.bind()
        # attach all relevant textures
        for t, tex in textures.items():
            glActiveTexture(GL_TEXTURE0+t)            
            glBindTexture(tex.target, tex.id)
        
        # set constant attribs
        for name,attrib in attribs.items():
            id = self.attribute_location(name)                
            if id<0:
                raise GLSLError("Could not find attribute %s in shader" % name)            
            glDisableVertexAttribArray(id)
            self.attribf(id, attrib)                   
        # set uniforms

        # note that the type must be right here!        
        for var, value in vars.items():
            self.__setitem__(var, value)
        np_vbo.draw_vao(vao, ibo, primitives=primitives,  n_vtxs=ibo.shape[0], n_prims=n_prims)
                
        self.unbind()

    #def setv(self, **kwargs):
    #    for k,v in kwargs.items():

    
    @property
    def active_uniforms(self):
        """Query OpenGL for a list of active uniforms.
  
        This is needed, because we are only allowed to set and query the
        values of active uniforms.
  
        """
        # Query number of active uniforms
        nr_uniforms = GLint()
        glGetProgramiv(self.handle, GL_ACTIVE_UNIFORMS,
                          byref(nr_uniforms))
        nr_uniforms = nr_uniforms.value
  
        length = GLsizei()
        size = GLsizei()
        enum = GLenum()
        name = create_string_buffer(self._ACTIVE_UNIFORM_MAX_LENGTH)
  
        uniforms = []
        for i in range(nr_uniforms):
            glGetActiveUniform(self.handle, i, 20, byref(length), byref(size),
                                  byref(enum), name)
            uniforms.append(name.value)
  
        return uniforms
  
    def _update_uniform_types(self):
        """Determine the numeric types of uniform variables.
  
        Updates the internal dictionary _uniform_type_info[var] with:
  
        kind : {'mat', 'vec', 'int', 'float'}
            The kind of numeric type.
        size : {2, 3, 4}
            The size of the type, e.g., 4 for vec4, 4 for mat2, 1 for scalar.
        array : bool
            Whether the variable is defined as an array, e.g.,
            uniform vec4 x[]; ==> true.
  
        """
        source = ";".join([s for s in self.srcs])
  
        # And look at each statement individually
        source = [s.strip() for s in source.split(';')]
  
        # Now look only at uniform declarations
        source = [s[len('uniform')+1:] for s in source if s.startswith('uniform')]
  
        types = [desc_name.split(' ')[:2] for desc_name in source]
  
        # Handle declarations of the form uniform float f=3.0
        types = [(desc, name.split('=')[0]) for (desc, name) in types]
  
        type_info = {}
  
        for desc, name in types:
            # Check for vector type, e.g. float x[12]
            name_array = name.split('[')
            var_name = name_array[0]
  
            # If array size is specified, see what it is
            if len(name_array) > 1:
                array_size = name_array[1].split(']')[0].strip()
                if not array_size:
                    raise RuntimeError("Array declaration without size is not "
                                       "supported.")
  
                array_size = int(array_size)
            else:
                array_size = 1
  
            # Check if type is, e.g., vec3
            vec_param = desc[-1]
            if vec_param.isdigit():
                size = int(vec_param)
                desc = desc[:-1]
            else:
                size = 1
  
            # For a square matrix, we have the side dimension.  To get
            # the size, we need to square that.
            if desc == 'mat':
                size *= size
  
            var_info = {
                'kind': desc,
                'size': size,
                'array': array_size}
  
            if type_info.has_key(var_name) and \
                   type_info[var_name] != var_info:
                raise GLSLError("Inconsistent definition of variable '%s'." % \
                                var_name)
            else:
                type_info[var_name] = var_info
  
        self._uniform_type_info = type_info
        print "\nUniforms:", " ".join(type_info.keys())
  

    def _uniform_loc_storage_and_type(self, var):
        """Return the uniform location and a container that can
        store its value.
  
        Parameters
        ----------
        var : string
            Uniform name.
  
        """
        if var not in self.active_uniforms:
            raise GLSLError("Uniform '%s' is not active.  Make sure the "
                            "variable is used in the source code." % var)
  
        try:
            var_info = self._uniform_type_info[var]
        except KeyError:
            raise ValueError("Uniform variable '%s' is not defined in "
                             "shader source." % var)
  
        # If this is an array, how many values are involved?
        count = var_info['array']
  
        if var_info['kind'] in ['int']:
            data_type = GLint
        else:
            data_type = GLfloat
  
        assert glIsProgram(self.handle) == True
        assert self.linked
  
        loc = glGetUniformLocation(self.handle, var)
  
        if loc == -1:
            raise RuntimeError("Could not query uniform location "
                               "for '%s'." % var)
  
        storage = data_type * (count * var_info['size'])
        storage_nested = count * (data_type * var_info['size'])
  
        return loc, storage, storage_nested, data_type
  
    @if_in_use
    def __setitem__(self, var, value):
        """Set uniform variable value.
  
        Please note that matrices must be specified in row-major format.
  
        """
        loc, container, container_nested, dtype = \
             self._uniform_loc_storage_and_type(var)

        
        var_info = self._uniform_type_info[var]
        count, kind, size = [var_info[k] for k in 'array', 'kind', 'size']
  
        # Ensure the value is given as a list
        try:
            value = list(value)
        except TypeError:
            value = [value]
  
        expected_size = var_info['size'] * var_info['array']
        if len(value) != var_info['size'] * var_info['array']:
            varname = var
            if var_info['array'] > 0:
                varname += '[%d]' % var_info['array']
            raise ValueError("Invalid input size (%s) for (%s) size '%s'." \
                             % (len(value), expected_size, varname))
  
        if var_info['kind'] == 'mat':
            set_func_name = 'glUniformMatrix%dfv' % np.sqrt(var_info['size'])
            set_func = getattr(gl, set_func_name)
            set_func(loc, count, True, container(*value))
        else:
            if var_info['kind'] == 'int':
                type_code = 'i'
            else:
                type_code = 'f'
  
            # Setter function, named something like glUniform4iv
            set_func_name = 'glUniform%d%sv' % (var_info['size'],
                                                type_code)
  
            set_func = getattr(gl, set_func_name)
            set_func(loc, count, container(*value))
  
    def __getitem__(self, var):
        """Get uniform value.
  
        """
        loc, container, container_nested, dtype = \
             self._uniform_loc_storage_and_type(var)
        var_info = self._uniform_type_info[var]
        data = container_nested()
  
        if dtype == GLint:
            get_func = glGetUniformiv
        else:
            get_func = glGetUniformfv
  
        alen = var_info['array']
        for i in range(alen):
            if i > 0:
                # Query the location of each array element
                loc = glGetUniformLocation(self.handle, var + '[%d]' % i)
  
            assert loc != -1
  
            get_func(self.handle, loc, data[i])
  
        # Convert to a NumPy array for easier processing
        data = np.array(data)
  
        # Scalar
        if data.size == 1:
            return data[0]
        # Array, matrix, vector
        elif var_info['kind'] == 'mat':
            count, n_sqr = data.shape
            n = np.sqrt(n_sqr)
  
            data = data.reshape((count, n, n), order='F')
  
        return data

class ShaderVBO:
    def __init__(self, shader, ibo, buffers=None, textures=None, attribs=None, vars=None, primitives=GL_QUADS):
        self.shader = shader        
        self.ibo = ibo
        
        self.buffers =  {}
        self.textures = {}
        self.tex_names = {}
        self.uniforms = {}
        self.primitives = primitives
        buffers = buffers or {}
        textures = textures or {}
        attribs = attribs or {}
        vars = vars or {}
        self.buffers_used = {}
        with self.shader as s:
            vbos = []
            
            # set the locations from the shader given the buffer names
            for name,vbuf in buffers.items():
                id = self.shader.attribute_location(name)                
                if id<0:
                    raise GLSLError("Could not find attribute %s in shader" % name)
                vbuf.id = id
                vbuf.name = name
                print("attr: %s -> %d" % (name, id))
                self.buffers[name] = vbuf
                vbos.append(vbuf)
                
            # bundle into a single vao
            self.vao = np_vbo.create_vao(vbos)

            # set constant attribs
            for name,attrib in attribs.items():
                id = self.shader.attribute_location(name)                
                if id<0:
                    raise GLSLError("Could not find attribute %s in shader" % name)
                        
                print("constant attr: %s" % name)
                glDisableVertexAttribArray(id)
                self.shader.attribf(id, attrib)                   
                
            for ix,(tex_name,tex) in enumerate(textures.items()):
                # set the sampler to the respective texture unit
                s.uniformi(tex_name, ix)       
                print("texture: %s -> active_texture_%d" % (tex_name, ix))
                self.tex_names[tex_name] = ix         
                self.textures[ix] = tex

            for var, value in vars.items():
                self.__setitem__(var, value)
        self.shader.unbind()

    def __setitem__(self, var, value):
        """Override setting uniforms so that they actually write to the shader,
        as if they were just ordinary variables"""
        if var in self.shader.active_uniforms:
            self.shader.__setitem__(var, value)

    def set_texture(self, name, texture):
        """Change the named texture to the given texture ID"""
        self.textures[self.tex_names[name]] = texture

    def draw(self, vars=None, n_prims=0, textures=None, primitives=None):
        vars = vars or {}

        primitives = primitives or self.primitives
        # either use the default textures

        if textures is None:
            textures = self.textures
        else:
            # or remap them here
            textures = {}
            for ix,(tex_name,tex) in enumerate(textures.items()):
                s.uniformi(tex_name, ix) 
                textures[ix] = tex

        self.shader.draw(vao=self.vao, ibo=self.ibo, textures=textures, vars=vars, n_prims=n_prims, primitives=self.primitives)
        
  
    

