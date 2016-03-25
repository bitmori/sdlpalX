# coding=utf-8
import io
from struct import unpack
from itertools import chain
import array
from itertools import chain
from Tkinter import *
from ttk import *
import tkMessageBox

class MKFDecoder:
    """
    MKF文件解码《仙剑》MKF文件的结构组成，以ABC.MKF为例：
    偏移         数据            含义
    00000000     6C 02 00 00     偏移表的长度，此值 / 4 - 2 = 包含文件个数
    00000004     6C 02 00 00     第1个子文件的偏移
    　     　                    第2-152个子件的偏移
    00000264     C2 6F 0F 00     第153个子文件的偏移
    00000268     64 9A 0F 00     此值指向文件末尾，也就是文件的长度
    0000026C     59 4A 5F 31     第1个子文件从这里开始，"YJ_1"是压缩文件的标志
    00000270     A0 08 00 00     这个值是文件的原始的长度
    00000274     12 07 00 00     这个值是文件压缩后的长度
    00000278     01 00           这个值是文件压缩占64K段的个数，通常为1
    0000027A     00 4A           这个值是数据压缩特征串表的长度
    0000027C     01 02 。。      从这开始是数据压缩特征串表
    000002C4     87 7B 02 4C     从这开始是压缩后的文件数据
    　     　                    其他压缩文件
    000F9A60     0B 12 80 38     文件的末尾
    """

    def __init__(self, path=None, data=None):
        # path和data不能同时是None
        assert path or data
        self.yj1 = YJ1Decoder()
        try:
            # 优先使用path（优先从文件读取）
            if path:
                f = open(path, 'rb')
                self.content = f.read()
            else:
                self.content = data
            # ===================================================================
            # 偏移（索引）表长度，假设文件前4位为6C 02 00 00（little-end的int值为
            # 26CH = 620），说明索引表长度为620字节，即620/4 = 155个整数，由于第一个
            # 整数被用于存储表长度，因此实际上只有后面154个整数存的是偏移量。另一方面，
            # 最后一个整数指向文件末尾，也就是文件的长度，因此实际上MKF内部的文件是由
            # 前后两个偏移量之间的byte表示的。这样由于一共有154个个偏移量，因此共有
            # 153个文件
            #
            # ！！！补充：第一个int（前四位）不仅是偏移表长度，也是第一个文件的开头
            # ABC.MFK中前面两个4位分别相等只是巧合（第一个文件为0）
            # ===================================================================
            self.count = unpack('I', self.content[:4])[0] / 4  # - 1
            self.indexes = []
            self.cache = {}
            for i in xrange(self.count):
                index = unpack('I', self.content[i << 2: (i + 1) << 2])[0]
                self.indexes.append(index)
            # 减去最后一个偏移量，对外而言，count就表示mkf文件中的子文件个数
            self.count -= 1
        except IOError:
            print 'error occurs when try to open file', path
        finally:
            if 'f' in dir():
                f.close()

    def check(self, index):
        assert index <= self.count and index >= 0

    def getFileCount(self):
        return self.count

    def isYJ1(self, index):
        '''
        判断文件是否为YJ_1压缩
        '''
        self.check(index)
        return self.content[self.indexes[index]:self.indexes[index] + 4] == '\x59\x4A\x5F\x31'

    def read(self, index):
        '''
        读取并返回指定文件，如果文件是经过YJ_1压缩的话，返回解压以后的内容
        '''
        self.check(index + 1)
        if not self.cache.has_key(index):
            data = self.content[self.indexes[index]:self.indexes[index + 1]]
            if self.isYJ1(index):
                data = self.yj1.decode(data)
            self.cache[index] = data
        return self.cache[index]

class YJ1Decoder:
    """
    YJ_1文件解析
    YJ_1文件结构：
    0000000: 594a5f31 fe520000 321b0000                02（即data[0xC]) 00 00 57（即data[0xF]）
              Y J _ 1 新文件长 源文件长（包含'YJ_1'头）block数                loop数
    """

    def __init__(self):
        pass

    def decode(self, data):
        '''
        解析YJ_1格式的压缩文件，如果文件不是YJ_1格式或者文件为空，则直接返回原始数据
        '''
        self.si = self.di = 0  # 记录文件位置的指针 记录解开后保存数据所在数组中的指向位置
        self.first = 1
        self.key_0x12 = self.key_0x13 = 0
        self.flags = 0
        self.flagnum = 0

        pack_length = 0
        ext_length = 0
        if not data:
            print 'no data to decode'
            return ''
        self.data = data
        self.dataLen = len(data)
        if self.readInt() != 0x315f4a59:  # '1' '_' 'J' 'Y'
            print 'not YJ_1 data'
            return data
        self.orgLen = self.readInt()
        self.fileLen = self.readInt()
        self.finalData = ['\x00' for _ in xrange(self.orgLen)]
        self.keywords = [0 for _ in xrange(0x14)]

        prev_src_pos = self.si
        prev_dst_pos = self.di

        blocks = self.readByte(0xC)

        self.expand()

        prev_src_pos = self.si
        self.di = prev_dst_pos
        for _ in xrange(blocks):
            if self.first == 0:
                prev_src_pos += pack_length
                prev_dst_pos += ext_length
                self.si = prev_src_pos
                self.di = prev_dst_pos
            self.first = 0

            ext_length = self.readShort()
            pack_length = self.readShort()

            if not pack_length:
                pack_length = ext_length + 4
                for _ in xrange(ext_length):
                    self.finalData[self.di] = self.data[self.si]
                    self.di += 1
                    self.si += 1
                ext_length = pack_length - 4
            else:
                d = 0
                for _ in xrange(0x14):
                    self.keywords[d] = self.readByte()
                    d += 1
                self.key_0x12 = self.keywords[0x12]
                self.key_0x13 = self.keywords[0x13]
                self.flagnum = 0x20
                self.flags = ((self.readShort() << 16) | self.readShort()) & 0xffffffff
                self.analysis()

        return ''.join([x for x in self.finalData if x != 0])

    def analysis(self):
        loop = 0
        numbytes = 0
        while True:
            loop = self.decodeloop()
            if loop == 0xffff:
                return
            for _ in xrange(loop):
                m = 0
                self.update(0x10)
                while True:
                    m = self.trans_topflag_to(m, self.flags, self.flagnum, 1)
                    self.flags = (self.flags << 1) & 0xffffffff
                    self.flagnum -= 1
                    if self.assist[m] == 0:
                        break
                    m = self.table[m]
                self.finalData[self.di] = chr(self.table[m] & 0xff)
                self.di += 1
            loop = self.decodeloop()
            if loop == 0xffff:
                return
            for _ in xrange(loop):
                numbytes = self.decodenumbytes()
                self.update(0x10)
                m = self.trans_topflag_to(0, self.flags, self.flagnum, 2)
                self.flags = (self.flags << 2) & 0xffffffff
                self.flagnum -= 2
                t = self.keywords[m + 8]
                n = self.trans_topflag_to(0, self.flags, self.flagnum, t)
                self.flags = (self.flags << t) & 0xffffffff
                self.flagnum -= t
                for _ in xrange(numbytes):
                    self.finalData[self.di] = self.finalData[self.di - n]
                    self.di += 1

    def readShort(self, si=None):
        if si:
            self.si = si
        if self.si >= self.dataLen:
            result = 0
        else:
            result, = unpack('H', self.data[self.si: self.si + 2])
        self.si += 2
        return result

    def readByte(self, si=None):
        if si:
            self.si = si
        if self.si >= self.dataLen:
            result = 0
        else:
            result, = unpack('B', self.data[self.si])
        self.si += 1
        return result

    def readInt(self, si=None):
        if si:
            self.si = si
        if self.si >= self.dataLen:
            result = 0
        else:
            result, = unpack('I', self.data[self.si: self.si + 4])
        self.si += 4
        return result

    def move_top(self, x):
        t = x >> 15
        return t & 0xffff

    def get_topflag(self, x, y):
        t = x >> 31
        return t & 0xffffffff

    def trans_topflag_to(self, x, y, z, n):
        for _ in xrange(n):
            x <<= 1
            x |= self.get_topflag(y, z)
            y = (y << 1) & 0xffffffff
            z -= 1
        return x & 0xffffffff

    def update(self, x):
        if self.flagnum < x:
            self.flags |= self.readShort() << (0x10 - self.flagnum) & 0xffffffff
            self.flagnum += 0x10

    def decodeloop(self):
        self.update(3)
        loop = self.key_0x12
        if self.get_topflag(self.flags, self.flagnum) == 0:
            self.flags = (self.flags << 1) & 0xffffffff
            self.flagnum -= 1
            t = 0
            t = self.trans_topflag_to(t, self.flags, self.flagnum, 2)
            self.flags = (self.flags << 2) & 0xffffffff
            self.flagnum -= 2
            loop = self.key_0x13
            if t != 0:
                t = self.keywords[t + 0xE]
                self.update(t)
                loop = self.trans_topflag_to(0, self.flags, self.flagnum, t)
                if loop == 0:
                    self.flags = (self.flags << t) & 0xffffffff
                    self.flagnum -= t
                    return 0xffff
                else:
                    self.flags = (self.flags << t) & 0xffffffff
                    self.flagnum -= t
        else:
            self.flags = (self.flags << 1) & 0xffffffff
            self.flagnum -= 1
        return loop

    def decodenumbytes(self):
        self.update(3)
        numbytes = self.trans_topflag_to(0, self.flags, self.flagnum, 2)
        if numbytes == 0:
            self.flags = (self.flags << 2) & 0xffffffff
            self.flagnum -= 2
            numbytes = (self.keywords[1] << 8) | self.keywords[0]
        else:
            self.flags = (self.flags << 2) & 0xffffffff
            self.flagnum -= 2
            if self.get_topflag(self.flags, self.flagnum) == 0:
                self.flags = (self.flags << 1) & 0xffffffff
                self.flagnum -= 1
                numbytes = (self.keywords[numbytes * 2 + 1] << 8) | self.keywords[numbytes * 2]
            else:
                self.flags = (self.flags << 1) & 0xffffffff
                self.flagnum -= 1
                t = self.keywords[numbytes + 0xB]
                self.update(t)
                numbytes = 0
                numbytes = self.trans_topflag_to(numbytes, self.flags, self.flagnum, t)
                self.flags = (self.flags << t) & 0xffffffff
                self.flagnum -= t
        return numbytes

    def expand(self):
        loop = self.readByte(0xF)
        offset, flags = 0, 0
        self.di = self.si
        self.si += 2 * loop
        self.table = []
        self.assist = []
        for _ in xrange(loop):
            if offset % 16 == 0:
                flags = self.readShort()
            self.table.append(unpack('B', self.data[self.di])[0])
            self.table.append(unpack('B', self.data[self.di + 1])[0])
            self.di += 2
            self.assist.append(self.move_top(flags))
            flags = (flags << 1) & 0xffff
            self.assist.append(self.move_top(flags))
            flags = (flags << 1) & 0xffff
            offset += 2

class PAL_Inventory:
    # inventory[0] => image in ball.mkf [0..232]
    # inventory[1] => price
    # inventory[2] => script when use
    # inventory[3] => script when equip
    # inventory[4] => script when throw
    # inventory[5] => property

    inventory_property_name = [
        '可使用', '可装备', '可投掷', '消耗品', '全体效果', '可典当',
        '李逍遥', '赵灵儿', '林月如', '巫后', '阿奴', '盖罗娇'
    ]

    beginAddressInSSS2 = 0x3D
    def __init__(self, data, objId):
        self.data = data
        self.objId = objId
        self.inventoryId = objId + PAL_Inventory.beginAddressInSSS2
        self.property = [0]*12
        self.init_property()

    def set_image_id(self, nid):
        self.data[0] = nid & 0xFFFF

    def get_image_id(self):
        return self.data[0]

    def set_price(self, price):
        self.data[1] = price & 0xFFFF

    def get_price(self):
        return self.data[1]

    def set_script_use(self, sid):
        self.data[2] = sid & 0xFFFF

    def get_script_use(self):
        return self.data[2]

    def set_script_equip(self, sid):
        self.data[3] = sid & 0xFFFF

    def get_script_equip(self):
        return self.data[3]

    def set_script_throw(self, sid):
        self.data[4] = sid & 0xFFFF

    def get_script_throw(self):
        return self.data[4]

    def init_property(self):
        for j in xrange(0, 12):
            self.property[j] = (self.data[5] & (1 << j)) >> j

    def set_property(self, prop, value):
        self.property[prop] = value & 1
        for j in xrange(0, 12):
            self.data[5] |= self.property[j] << j

    def set_properties(self, props):
        self.property = props
        for j in xrange(0, 12):
            self.data[5] |= self.property[j] << j

def get_chunks(l, n):
    llen = len(l)
    return [l[i:i+n] for i in xrange(0, llen, n)]

class WordData:
    def __init__(self):
        self.changed = False
        with open('WORD.DAT', mode='rb') as file: # b is important -> binary
            fileContent = file.read()
            theBuffer = get_chunks(fileContent, 10)
            self.words = [ss.strip().decode('big5').encode('utf8') for ss in theBuffer]

    def __enter__(self):
        return self

    def __exit__(self, type, value, trace):
        if self.changed:
            self.write_to_file('WORDEX.DAT')

    def get_object_name(self, objId):
        return self.words[objId]

    def set_object_name(self, objId, name):
        self.changed = True
        self.words[objId] = name

    def add_object_name(self, name):
        self.changed = True
        self.words.append(name)
        return len(self.words)

    def words_to_str(self):
        biglist = ["{:10}".format(ss.decode('utf8').encode('big5')) for ss in self.words]
        return biglist

    def write_to_file(self, filename):
        with open(filename, mode='wb') as file:
            for ss in self.words_to_str():
                file.write(ss)

class App:
    def __init__(self):
        self.sss = MKFDecoder(path='./SSS.MKF', data=None)
        self.arrayH = array.array('H', self.sss.read(2))
        self.allObjDef = get_chunks(self.arrayH, 6)
        i = 0
        self.inventories = [PAL_Inventory(obj, i) for i, obj in enumerate(self.allObjDef[0x3D:0x127])]
        # self.magics = [PAL_Magic(obj) for obj in self.allObjDef[0x127:0x18E]]
        # self.monsters = [PAL_Monster(obj) for obj in self.allObjDef[0x18E:0x227]]
        # self.poisons = [PAL_Poison(obj) for obj in self.allObjDef[0x227:0x235]

    def __enter__(self):
        return self

    def __exit__(self, type, value, trace):
        pass

    def save_inventory(self, filename):
        # TODO - finish the correct saving procedure
        newFileByteArray = bytearray(list(chain.from_iterable(self.allObjDef)))
        newFile = open ("./sss2.bin", "wb")
        newFile.write(newFileByteArray)
        newFile.close()

    def change_object_name(self, objId, name, word_data):
        word_data.set_object_name(objId, name)

    def add_object(self, type, name, obj, word_data):
        pass

class PALEditorUI(Frame):
    def __init__(self, app_data, word_data, isapp=True, name='palEditor'):
        Frame.__init__(self, name=name)
        self.pack(expand=Y, fill=BOTH)
        self.master.title('Notebook Demo')
        self.master.geometry('200x100')
        self.master.minsize(width=530, height=600)
        self.isapp = isapp
        self.app = app_data
        self.word = word_data
        self.currentInventory = None
        self._create_widgets()

    def _create_widgets(self):
        mainPanel = Frame(self, name='mainPanel')
        mainPanel.pack(side=TOP, fill=BOTH, expand=Y, pady=(0, 30))

        # create the notebook
        nb = Notebook(mainPanel, name='notebook')

        # # extend bindings to top level window allowing
        # #   CTRL+TAB - cycles thru tabs
        # #   SHIFT+CTRL+TAB - previous tab
        # #   ALT+K - select tab using mnemonic (K = underlined letter)
        # nb.enable_traversal()

        nb.pack(fill=BOTH, expand=Y)
        self._create_tab_inventory(nb)
        self._create_tab_magic(nb)
        self._create_tab_monster(nb)

    def _create_tab_inventory(self, nb):
        frame = Frame(nb)

        listBoxFrame = Frame(frame, width=130)
        scrollbar = Scrollbar(listBoxFrame)
        scrollbar.pack(side=RIGHT, fill=Y)
        listbox = Listbox(listBoxFrame, name='inventoryList', yscrollcommand=scrollbar.set, selectmode=SINGLE)
        for inv in self.app.inventories:
            listbox.insert(END, self.word.get_object_name(inv.inventoryId))
        listbox.pack(side=LEFT, fill=BOTH)
        scrollbar.config(command=listbox.yview)
        listBoxFrame.pack(side=LEFT, fill=Y)

        objectDataFrame = Frame(frame)
        Label(objectDataFrame, text="道具信息").grid(row=0, columnspan=2)

        Label(objectDataFrame, text="道具名称：").grid(row=1,column=0, sticky=W)
        inventoryNameVar = StringVar()
        inventoryName = Entry(objectDataFrame, textvariable=inventoryNameVar)
        inventoryName.grid(row=1,column=1)

        Label(objectDataFrame, text="道具价格：").grid(row=2, column=0, sticky=W)
        inventoryPriceVar = StringVar()
        inventoryPrice = Entry(objectDataFrame, textvariable=inventoryPriceVar)
        inventoryPrice.grid(row=2, column=1, sticky=E)

        Label(objectDataFrame, text="使用脚本：").grid(row=3, column=0, sticky=W)
        inventoryUseScriptVar = StringVar()
        inventoryUseScript = Entry(objectDataFrame, textvariable=inventoryUseScriptVar)
        inventoryUseScript.grid(row=3, column=1, sticky=E)

        Label(objectDataFrame, text="装备脚本：").grid(row=4, column=0, sticky=W)
        inventoryEquipScriptVar = StringVar()
        inventoryEquipScript = Entry(objectDataFrame, textvariable=inventoryEquipScriptVar)
        inventoryEquipScript.grid(row=4, column=1, sticky=E)

        Label(objectDataFrame, text="投掷脚本：").grid(row=5, column=0, sticky=W)
        inventoryThrowScriptVar = StringVar()
        inventoryThrowScript = Entry(objectDataFrame, textvariable=inventoryThrowScriptVar)
        inventoryThrowScript.grid(row=5, column=1, sticky=E)

        Label(objectDataFrame, text="道具属性：").grid(row=6, columnspan=2, sticky=W)
        inventoryProperties = [IntVar() for i in xrange(12)]
        r = 6
        for i in xrange(12):
            if i % 2 == 0:
                r = r + 1
            Checkbutton(objectDataFrame, text=PAL_Inventory.inventory_property_name[i], variable=inventoryProperties[i]).grid(row=r, column=(i % 2), sticky=W)

        Label(objectDataFrame, text="道具图像：").grid(row=r+1, column=0, sticky=W)
        inventoryImageIdVar = StringVar()
        Entry(objectDataFrame, textvariable=inventoryImageIdVar).grid(row=r+1, column=1)

        labelImage = Label(objectDataFrame, text="HAHA")
        labelImage.grid(row=r+2, column=0, columnspan=2, rowspan=2, sticky=W+E+N+S, padx=5, pady=5)

        def onSaveButtonCallback():
            if self.currentInventory == None:
                tkMessageBox.showerror("Error", "Please select the inventory you want to change")
            else:
                newPrice = int(inventoryPriceVar.get())
                if (self.currentInventory.get_price() != newPrice and newPrice <= 0xFFFF and newPrice >= 0):
                    self.currentInventory.set_price(newPrice)
                newName = inventoryNameVar.get()
                oldName = self.word.get_object_name(self.currentInventory.inventoryId)
                if (oldName != newName):
                    self.word.set_object_name(self.currentInventory.inventoryId, newName)
                self.currentInventory.set_properties([p.get() for p in inventoryProperties])

        Button(objectDataFrame, text='SAVE!', command=onSaveButtonCallback).grid(row=r+3, column=0)

        objectDataFrame.pack(side=RIGHT, fill=Y)

        def onSelect(ev):
            w = ev.widget
            index = int(w.curselection()[0])
            inventoryNameVar.set(w.get(index))
            self.currentInventory = self.app.inventories[index]
            inventoryImageIdVar.set(hex(self.currentInventory.get_image_id()))
            inventoryPriceVar.set(self.currentInventory.get_price())
            inventoryUseScriptVar.set(hex(self.currentInventory.get_script_use()))
            inventoryEquipScriptVar.set(hex(self.currentInventory.get_script_equip()))
            inventoryThrowScriptVar.set(hex(self.currentInventory.get_script_throw()))

            for i in xrange(12):
                inventoryProperties[i].set(self.currentInventory.property[i])

        listbox.bind('<<ListboxSelect>>', onSelect)

        nb.add(frame, text='Inventory', padding=5)

    # =============================================================================
    def _create_tab_magic(self, nb):
        frame = Frame(nb)

        myframe=Frame(frame, width=130)
        scrollbar = Scrollbar(myframe)
        scrollbar.pack(side=RIGHT, fill=Y)
        listbox = Listbox(myframe, yscrollcommand=scrollbar.set)
        for line in xrange(100):
            listbox.insert(END, "This is line number %d" % line)
        listbox.pack( side = LEFT, fill = BOTH )
        scrollbar.config(command=listbox.yview)
        myframe.pack(side=LEFT, fill=Y)

        nb.add(frame, text='Magic', padding=5)


    # =============================================================================
    def _create_tab_monster(self, nb):
        # ad hoc all view!
        frame = Frame(nb)

        listBoxFrame = Frame(frame, width=130)
        scrollbar = Scrollbar(listBoxFrame)
        scrollbar.pack(side=RIGHT, fill=Y)
        listbox = Listbox(listBoxFrame, name='inventoryList', yscrollcommand=scrollbar.set, selectmode=SINGLE)
        for i, obj in enumerate(self.app.allObjDef):
            listbox.insert(END, self.word.get_object_name(i))
        listbox.pack(side=LEFT, fill=BOTH)
        scrollbar.config(command=listbox.yview)
        listBoxFrame.pack(side=LEFT, fill=Y)

        objectDataFrame = Frame(frame)
        Label(objectDataFrame, text="道具信息").grid(row=0, column=0)
        T = Text(objectDataFrame, height=3, width=30)
        T.grid(row=1, column=0)
        # T.insert(0, '')

        objectDataFrame.pack(side=LEFT, fill=Y)

        def onSelect(ev):
            w = ev.widget
            index = int(w.curselection()[0])
            T.delete('1.0', END)
            T.insert('1.0', ["{0:#0{1}x}".format(i,6) for i in self.app.allObjDef[index]])
            # inventoryNameVar.set(w.get(index))
            # self.currentInventory = self.app.inventories[index]
            # inventoryImageIdVar.set(hex(self.currentInventory.get_image_id()))
            # inventoryPriceVar.set(self.currentInventory.get_price())
            # inventoryUseScriptVar.set(hex(self.currentInventory.get_script_use()))
            # inventoryEquipScriptVar.set(hex(self.currentInventory.get_script_equip()))
            # inventoryThrowScriptVar.set(hex(self.currentInventory.get_script_throw()))
            #
            # for i in xrange(12):
            #     inventoryProperties[i].set(self.currentInventory.property[i])

        listbox.bind('<<ListboxSelect>>', onSelect)

        nb.add(frame, text='Monster', padding=5)


if __name__ == '__main__':
    with WordData() as word, App() as app:
        PALEditorUI(app, word).mainloop()
    # with window("This is a window"):
    #     label(word.get_object_name(objId=app.inventories[2].inventoryId), font = "Verdana 24 bold underline")
    #     lb = listBox(height=3, values=[i for i in xrange(9)])
    #     scrollbar = Scrollbar(root)
    #     scrollbar.pack(side=RIGHT, fill=Y)
    #
    #     listbox = Listbox(root)
    #     listbox.pack()
