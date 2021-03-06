#   Copyright (c) 2003-2006 Open Source Applications Foundation
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.


from application import schema
from osaf import pim

class MyKind1(pim.ContentItem):
    """An example content kind"""
    
    attr1 = schema.One(schema.Text)
    attr2 = schema.One(schema.Text)
  
    # Typical clouds include a "copying" cloud, and a "sharing" cloud

    schema.addClouds(
        sharing = schema.Cloud(
            literal = [attr1, attr2],
            byValue = [attr3],
            byCloud = [attr4]
        )
    )

def installParcel(parcel, oldVersion=None):
    # create an instance of MyKind, named 'anItem', in the parcel
    MyKind1.update(
        parcel, "anItem",
        attr1 = "Setting custom attributes is simple",
    )

