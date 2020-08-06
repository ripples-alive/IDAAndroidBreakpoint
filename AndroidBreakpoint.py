import idaapi
import idc
import struct

def get_ushort(file,offset):
    file.seek(offset)
    return struct.unpack("H",file.read(2))[0]

def get_ulong(file,offset):
    file.seek(offset)
    return struct.unpack("L",file.read(4))[0]


def static_breakpoint(target_type):
    try:
        base = idc.FirstSeg()
        if base == idc.BADADDR:
            print("can't find first seg")
            return
        filepath = idaapi.get_input_file_path()
        print("filename:", filepath)
        idbFile = open(filepath, "rb")
        e_phoff = get_ushort(idbFile, 0x1C)
        e_phentsize = get_ushort(idbFile, 0x2A)
        e_phnum = get_ushort(idbFile, 0x2C)
        print(e_phoff, e_phentsize, e_phnum)
        dynamic = -1
        for i in xrange(e_phnum):
            idbFile.seek(e_phoff + e_phentsize * i)
            p_type = get_ulong(idbFile, e_phoff + e_phentsize * i)
            # define PT_DYNAMIC 2
            if p_type == 2:
                dynamic = get_ulong(idbFile, e_phoff + e_phentsize * i + 4)
                break
        if dynamic == -1:
            print("\tcan't find dynamic")
            return
        dynamic_type = get_ulong(idbFile, dynamic)
        init = -1

        while dynamic_type != 0:

            dynamic += 8
            dynamic_type = get_ulong(idbFile, dynamic)

            if dynamic_type == target_type:
                init = get_ulong(idbFile, dynamic + 4)
                break
        if init == -1:
            print("\tcan't find init")
            return
        idc.AddBpt(base + init)
        print('\tbp the init on the %x' % (base + init))
        print("\nbp init finished")
    except BaseException as e:
        print(e)


#linker call init and init_array functions
# .text:00002924 14 49                       LDR             R1, =(aLinker - 0x2930)
# .text:00002926 04 20                       MOVS            R0, #4
# .text:00002928 23 46                       MOV             R3, R4
# .text:0000292A 14 4A                       LDR             R2, =(aSCallingCons_0 - 0x2932)
# .text:0000292C 79 44                       ADD             R1, PC  ; "linker"
# .text:0000292E 7A 44                       ADD             R2, PC  ; "\"%s\": calling constructors"
# .text:00002930 01 F0 E6 FE                 BL              sub_4700
# .text:00002934
# .text:00002934             loc_2934                                ; CODE XREF: sub_2884+52j
# .text:00002934 12 49                       LDR             R1, =(aDt_init - 0x2940)
# .text:00002936 20 46                       MOV             R0, R4
# .text:00002938 D4 F8 F0 20                 LDR.W           R2, [R4,#0xF0]
# .text:0000293C 79 44                       ADD             R1, PC  ; "DT_INIT"
# .text:0000293E FF F7 DF FE                 BL              sub_2700
# .text:00002942 10 49                       LDR             R1, =(aDt_init_array - 0x2956)
# .text:00002944 00 20                       MOVS            R0, #0
# .text:00002946 00 90                       STR             R0, [SP,#0x28+var_28]
# .text:00002948 20 46                       MOV             R0, R4
# .text:0000294A D4 F8 E0 20                 LDR.W           R2, [R4,#0xE0]
# .text:0000294E D4 F8 E4 30                 LDR.W           R3, [R4,#0xE4]
# .text:00002952 79 44                       ADD             R1, PC  ; "DT_INIT_ARRAY"
# .text:00002954 FF F7 0E FF                 BL              sub_2774
# .text:00002958
# .text:00002958             locret_2958                             ; CODE XREF: sub_2884+Cj
# .text:00002958 BD E8 FE 83                 POP.W           {R1-R9,PC}
def dynamic_breakpoint(targe_type):
    has_linker = False
    module_base = idc.GetFirstModule()
    while module_base != None:
        module_name = idc.GetModuleName(module_base)
        if module_name.find('linker') >= 0:
            has_linker = True
            break

        module_base = idc.GetNextModule(module_base)

    if has_linker == False:
        print('[*]unable to find linker module base')
        return

    module_size = idc.GetModuleSize(module_base)
    print('[*]found linker base=>0x%08X, Size=0x%08X' % (module_base, module_size))

    print("\t[-]begin to search DT_INIT")
    init_func_ea = 0
    init_array_ea = 0
    # bytecode=b'\x53\x1e\x73\xb5\x03\x33\x06\x46\x0d\x46\x14\x46\x24\xd8\x13\x48\x78\x44\x01\x68\x01\x29'
    bytecode =[0x14,0x49,0x04,0x20,0x23,0x46,0x14,0x4A,0x79,0x44,0x7A,0x44]
    findcode=True
    for ea_offset in range(module_base, module_base + module_size):
        findcode = True
        for i in xrange(len(bytecode)):
            if idaapi.get_byte(ea_offset+i)!=bytecode[i]:
                findcode=False
                break
        if(findcode==True):
            init_func_ea=ea_offset+0x1A
            init_array_ea=ea_offset+0x30
            break
    if(findcode==False):
        print("can't find bytecode")
        return
    print("\t[-]found INIT=>0x%08X INIT_ARRAY=>0x%08X" % (init_func_ea, init_array_ea))
    print("\t[-]try set breakpoint there")
    if targe_type==12:
        idc.AddBpt(init_func_ea)
    if targe_type==25:
        idc.AddBpt(init_array_ea)
    print("[*]script finish")

class bpInit(idaapi.action_handler_t):
    name = "bpInit"
    lable = "bpInit"
    hotkey = None

    def __init__(self):
        idaapi.action_handler_t.__init__(self)

    def activate(self, ctx):
        print("\n.init handler activate")
        idainfo = idaapi.get_inf_structure()
        if idainfo.filetype != idaapi.f_ELF:
            print("\tidb isn't elf,skip")
            return
        if idaapi.is_debugger_on():
            print("\tdebugger is on,prepare to bp by linker.")
            dynamic_breakpoint(12)
        else:
            print("\tdebugger isn't on ,prepare to bp by search the elf program header")
            # define DT_INIT 12
            static_breakpoint(12)

    def update(self, ctx):
        print(".init handler update")
        return idaapi.AST_ENABLE_ALWAYS

class bpInitArray(idaapi.action_handler_t):
    name = "bpInitArray"
    lable = "bpInitArray"
    hotkey = None
    def __init__(self):
        idaapi.action_handler_t.__init__(self)

    def activate(self, ctx):
        print("init array handler activate")
        idainfo = idaapi.get_inf_structure()
        if idainfo.filetype != idaapi.f_ELF:
            print("\tidb isn't elf,skip")
            return
        if idaapi.is_debugger_on():
            print("\tdebugger is on,prepare to bp by linker.")
            dynamic_breakpoint(25)
        else:
            print("\tdebugger isn't on ,prepare to bp by search the elf program header")
            # define DT_INIT_ARRAY	25
            static_breakpoint(25)

    def update(self, ctx):
        print("init array handler update")
        return idaapi.AST_ENABLE_ALWAYS

def register(action,*args):
    idaapi.register_action(
        idaapi.action_desc_t(
            action.name,
            action.lable,
            action(*args),
            action.hotkey,
            "set breakpoint on the .init function",
        )
    )

class myIdaPlugin(idaapi.plugin_t):
    flags = idaapi.PLUGIN_KEEP
    wanted_name = "AndroidBreakpoint"
    wanted_hotkey = "Alt-F9"
    comment = "usual bp in android"
    help = "Something helpful"

    def init(self):
        print("init func")
        try:
            # result=idaapi.register_and_attach_to_menu("Options/path","name","label","",0,self.run(0),None)
            register(bpInit)
            register(bpInitArray)
            idaapi.attach_action_to_menu("Edit/AndroidBreakpoint/",bpInit.name,idaapi.SETMENU_APP)
            idaapi.attach_action_to_menu("Edit/AndroidBreakpoint/", bpInitArray.name, idaapi.SETMENU_APP)
        except BaseException as e:
            print(e)

        idainfo=idaapi.get_inf_structure()
        if idainfo.filetype!=idaapi.f_ELF:
            print("idb isn't elf,skip")
            return idaapi.PLUGIN_SKIP
        return idaapi.PLUGIN_KEEP

    def term(self):
        pass

    def run(self, arg):
        try:
            print("AndroidBreakpoint run")
        except BaseException as e:
            print(e)

def PLUGIN_ENTRY():

    return myIdaPlugin()
