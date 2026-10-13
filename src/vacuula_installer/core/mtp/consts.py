from __future__ import annotations

from enum import IntEnum


class ContainerType(IntEnum):
    Undefined = 0x0000
    Command = 0x0001
    Data = 0x0002
    Response = 0x0003
    Event = 0x0004


class Operations(IntEnum):
    GetDeviceInfo = 0x1001
    OpenSession = 0x1002
    CloseSession = 0x1003
    GetStorageIDs = 0x1004
    GetStorageInfo = 0x1005
    GetNumObjects = 0x1006
    GetObjectHandles = 0x1007
    GetObjectInfo = 0x1008
    GetObject = 0x1009
    GetThumb = 0x100A
    DeleteObject = 0x100B
    SendObjectInfo = 0x100C
    SendObject = 0x100D
    InitiateCapture = 0x100E
    FormatStore = 0x100F
    ResetDevice = 0x1010
    SelfTest = 0x1011
    SetObjectProtection = 0x1012
    PowerDown = 0x1013
    GetDevicePropDesc = 0x1014
    GetDevicePropValue = 0x1015
    SetDevicePropValue = 0x1016
    ResetDevicePropValue = 0x1017
    TerminateOpenCapture = 0x1018
    MoveObject = 0x1019
    CopyObject = 0x101A
    GetPartialObject = 0x101B
    InitiateOpenCapture = 0x101C
    GetObjectPropsSupported = 0x9801
    GetObjectPropDesc = 0x9802
    GetObjectPropValue = 0x9803
    SetObjectPropValue = 0x9804
    GetObjectReferences = 0x9810
    SetObjectReferences = 0x9811
    Skip = 0x9820


class Response(IntEnum):
    Undefined = 0x2000
    OK = 0x2001
    General_Error = 0x2002
    Session_Not_Open = 0x2003
    Invalid_TransactionID = 0x2004
    Operation_Not_Supported = 0x2005
    Parameter_Not_Supported = 0x2006
    Incomplete_Transfer = 0x2007
    Invalid_StorageID = 0x2008
    Invalid_ObjectHandle = 0x2009
    DeviceProp_Not_Supported = 0x200A
    Invalid_ObjectFormatCode = 0x200B
    Store_Full = 0x200C
    Object_WriteProtected = 0x200D
    Store_ReadOnly = 0x200E
    Access_Denied = 0x200F
    No_Thumbnail_Present = 0x2010
    SelfTest_Failed = 0x2011
    Partial_Deletion = 0x2012
    Store_Not_Available = 0x2013
    Specification_By_Format_Unsupported = 0x2014
    No_Valid_ObjectInfo = 0x2015
    Invalid_Code_Format = 0x2016
    Unknown_Vendor_Code = 0x2017
    Capture_Already_Terminated = 0x2018
    Device_Busy = 0x2019
    Invalid_ParentObject = 0x201A
    Invalid_DeviceProp_Format = 0x201B
    Invalid_DeviceProp_Value = 0x201C
    Invalid_Parameter = 0x201D
    Session_Already_Open = 0x201E
    Transaction_Cancelled = 0x201F
    Specification_of_Destination_Unsupported = 0x2020
    Invalid_ObjectPropCode = 0xA801
    Invalid_ObjectProp_Format = 0xA802
    Invalid_ObjectProp_Value = 0xA803
    Invalid_ObjectReference = 0xA804
    Group_Not_Supported = 0xA805
    Invalid_Dataset = 0xA806
    Specification_By_Group_Unsupported = 0xA807
    Specification_By_Depth_Unsupported = 0xA808
    Object_Too_Large = 0xA809
    ObjectProp_Not_Supported = 0xA80A


class DeviceProperties(IntEnum):
    Undefined = 0x5000
    Battery_Level = 0x5001
    Functional_Mode = 0x5002
    Image_Size = 0x5003
    Compression_Setting = 0x5004
    White_Balance = 0x5005
    RGB_Gain = 0x5006
    F_Number = 0x5007
    Focal_Length = 0x5008
    Focus_Distance = 0x5009
    Focus_Mode = 0x500A
    Exposure_Metering_Mode = 0x500B
    Flash_Mode = 0x500C
    Exposure_Time = 0x500D
    Exposure_Program_Mode = 0x500E
    Exposure_Index = 0x500F
    Exposure_Bias_Compensation = 0x5010
    DateTime = 0x5011
    Capture_Delay = 0x5012
    Still_Capture_Mode = 0x5013
    Contrast = 0x5014
    Sharpness = 0x5015
    Digital_Zoom = 0x5016
    Effect_Mode = 0x5017
    Burst_Number = 0x5018
    Burst_Interval = 0x5019
    Timelapse_Number = 0x501A
    Timelapse_Interval = 0x501B
    Focus_Metering_Mode = 0x501C
    Upload_URL = 0x501D
    Artist = 0x501E
    Copyright_Info = 0x501F
    Synchronization_Partner = 0xD401
    Device_Friendly_Name = 0xD402
    Volume = 0xD403
    SupportedFormatsOrdered = 0xD404
    DeviceIcon = 0xD405
    Playback_Rate = 0xD410
    Playback_Object = 0xD411
    Playback_Container_Index = 0xD412
    Session_Initiator_Version_Info = 0xD406
    Perceived_Device_Type = 0xD407
