# valuerep.py
#PZ downloaded 6 Feb 2012
"""Special classes for DICOM value representations (VR)"""
# Copyright (c) 2008-2012 Darcy Mason
# This file is part of pydicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pydicom.googlecode.com

from decimal import Decimal
import dicom.config
from dicom.multival import MultiValue

#PZ
import sys
#PZ maybe hexversion is better
if sys.hexversion >= 0x02060000 and sys.hexversion < 0x03000000: 
    inPy26 = True
else: 
    inPy26 = False

if sys.hexversion >= 0x03000000: 
    inPy3 = True
else: 
    inPy3 = False
#PZ 
if inPy26:
    namebase = bytestring
    strbase = basestring    
if inPy3:
    unicode = str
    namebase = object
    bytestring = bytes
    basestring = str
    strbase = str    
#PZ it cannot work in Py3 sincethere is no bytestring    
"""
from sys import version_info
if version_info[0] < 3:
    namebase = object
    bytestring = str
    strbase = str
else:
    namebase = bytestring
    strbase = basestring
"""
    
def is_stringlike(name):
    """Return True if name is string-like."""
#PZ similar to isString(val): from dataelem.py
#PZ Both will fail if passed tag since Basetag implements __str__()
    try:
#PZstartswith is be    
        name.startswith(" ")
#        name + ""
#    except TypeError:
    except:    
        return False
    else:
        return True

class DS(Decimal):
    """Store values for DICOM VR of DS (Decimal String).
    Note: if constructed by an empty string, returns the empty string,
    not an instance of this class.
    """
    def __new__(cls, val):
        """Create an instance of DS object, or return a blank string if one is
        passed in, e.g. from a type 2 DICOM blank value.
        """
        # DICOM allows spaces around the string, but python doesn't, so clean it
        if isinstance(val, strbase):
            val=val.strip()
        if val == '':
            return val
        if isinstance(val, float) and not dicom.config.allow_DS_float:
            msg = ("DS cannot be instantiated with a float value, unless "
                "config.allow_DS_float is set to True. It is recommended to "
                "convert to a string instead, with the desired number of digits, "
                "or use Decimal.quantize and pass a Decimal instance.")
#PZ 3109/3110                
            raise TypeError(msg)
        if not isinstance(val, Decimal):
            val = super(DS, cls).__new__(cls, val)
        if len(str(val)) > 16 and dicom.config.enforce_valid_values:
            msg = ("DS value representation must be <= 16 characters by DICOM "
                "standard. Initialize with a smaller string, or set config.enforce_valid_values "
                "to False to override, "
                "or use Decimal.quantize() and initialize with a Decimal instance.")
#PZ 3109/3110                
            raise OverflowError(msg)
        return val
    def __init__(self, val):
        """Store the original string if one given, for exact write-out of same 
        value later. E.g. if set '1.23e2', Decimal would write '123', but DS
        will use the original
        """ 
        # ... also if user changes a data element value, then will get
        # a different Decimal, as Decimal is immutable.
        if isinstance(val, strbase):
            self.original_string = val
            
    def __repr__(self):
        if hasattr(self, 'original_string'):
            return "'" + self.original_string + "'"
        else:
            return "'" + super(DS,self).__str__() + "'"
        
class IS(int):
    """Derived class of int. Stores original integer string for exact rewriting 
    of the string originally read or stored.
    
    Don't use this directly; call the IS() factory function instead.
    """
    # Unlikely that str(int) will not be the same as the original, but could happen
    # with leading zeros.
    def __new__(cls, val):
        """Create instance if new integer string"""
        if isinstance(val, strbase) and val.strip() == '':
            return ''
        newval = super(IS, cls).__new__(cls, val)
        # check if a float or Decimal passed in, then could have lost info,
        # and will raise error. E.g. IS(Decimal('1')) is ok, but not IS(1.23)
        if isinstance(val, (float, Decimal)) and newval != val:
#PZ 3109/3110        
            raise TypeError( "Could not convert value to integer without loss")
                # Checks in case underlying int is >32 bits, DICOM does not allow this
        if (newval < -2**31 or newval >= 2**31) and dicom.config.enforce_valid_values:
            message = "Value exceeds DICOM limits of -2**31 to (2**31 - 1) for IS"
#PZ 3109/3110            
            raise OverflowError( message)
        return newval
    def __init__(self, val):
        # If a string passed, then store it
#PZ changed to strbase        
        if isinstance(val, strbase):
            self.original_string = val
    def __repr__(self):
        if hasattr(self, 'original_string'):
            return "'" + self.original_string + "'"
        else:
            return "'" + int.__str__(self) + "'"
            
def MultiString(val, valtype=str):
    """Split a string by delimiters if there are any
    
    val -- DICOM string to split up
    valtype -- default str, but can be e.g. UID to overwrite to a specific type
    """
    # Remove trailing blank used to pad to even length
    # 2005.05.25: also check for trailing 0, error made in PET files we are converting
#PZ run in unicode or forget about string functions    
    val = val.decode()
    if val and (val.endswith(' ') or val.endswith('\x00')):
        val = val[:-1]

    # XXX --> simpler version python > 2.4   splitup = [valtype(x) if x else x for x in val.split("\\")]
    splitup = []
    for subval in val.split("\\"):
        if subval:
            splitup.append(valtype(subval))
        else:
            splitup.append(subval)
    if len(splitup) == 1:
        return splitup[0]
    else:
        return MultiValue(valtype, splitup)

class PersonNameBase(namebase):
    """Base class for Person Name classes"""

    def __init__(self, val):
        """Initialize the PN properties"""
        # Note normally use __new__ on subclassing an immutable, but here we just want 
        #    to do some pre-processing for properties
        # PS 3.5-2008 section 6.2 (p.28)  and 6.2.1 describes PN. Briefly:
        #  single-byte-characters=ideographic characters=phonetic-characters
        # (each with?):
        #   family-name-complex^Given-name-complex^Middle-name^name-prefix^name-suffix
        self.parse()

    def formatted(self, format_str):
        """Return a formatted string according to the format pattern
        
        Use "...%(property)...%(property)..." where property is one of
           family_name, given_name, middle_name, name_prefix, name_suffix
        """
        return format_str % self.__dict__
    def parse(self):
        """Break down the components and name parts"""
        self.components = self.split("=")
        nComponents = len(self.components)
        self.single_byte = self.components[0]
        self.ideographic = ''
        self.phonetic = ''
        if nComponents > 1:
            self.ideographic = self.components[1]
        if nComponents > 2:
            self.phonetic = self.components[2]
        
        if self.single_byte:
            name_string = self.single_byte+"^^^^" # in case missing trailing items are left out
            parts = name_string.split("^")[:5]
            (self.family_name, self.given_name, self.middle_name,
                               self.name_prefix, self.name_suffix) = parts
        else:
            (self.family_name, self.given_name, self.middle_name, 
                self.name_prefix, self.name_suffix) = ('', '', '', '', '')

    
class PersonName(PersonNameBase, str):
    """Human-friendly class to hold VR of Person Name (PN)

    Name is parsed into the following properties:
    single-byte, ideographic, and phonetic components (PS3.5-2008 6.2.1)
    family_name,
    given_name,
    middle_name,
    name_prefix,
    name_suffix
    
    """
    def __new__(cls, val):
        """Return instance of the new class"""
        # Check if trying to convert a string that has already been converted 
        if isinstance(val, PersonName):
            return val
        return super(PersonName, cls).__new__(cls, val)
    def family_comma_given(self):
        """Return name as 'Family-name, Given-name'"""
        return self.formatted("%(family_name)s, %(given_name)s")
    # def __str__(self):
        # return str(self.byte_string)
        # XXX need to process the ideographic or phonetic components?
    # def __len__(self):
        # return len(self.byte_string)


        
class PersonNameUnicode(PersonNameBase, unicode):
    """Unicode version of Person Name"""
    def __new__(cls, val, encodings):
        """Return unicode string after conversion of each part
        val -- the PN value to store
        encodings -- a list of python encodings, generally found
                 from dicom.charset.python_encodings mapping
                 of values in DICOM data element (0008,0005).
        """
        # Make the possible three character encodings explicit:        

        if not isinstance(encodings, list):
            encodings = [encodings]*3
        if len(encodings) == 2:
            encodings.append(encodings[1])
        # print encodings
        components = val.split("=")
        unicomponents = [unicode(components[i],encodings[i]) 
                            for i, component in enumerate(components)]
#PZ u by default                            
        new_val = "=".join(unicomponents)

        return unicode.__new__(cls, new_val)
    def __init__(self, val, encodings):
        self.encodings = encodings
        PersonNameBase.__init__(self, val)
    def family_comma_given(self):
        """Return name as 'Family-name, Given-name'"""
        return self.formatted("%(family_name)u, %(given_name)u")

class OtherByte(bytestring):
    pass
