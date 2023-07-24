import argparse
import itertools
import re
import os

parser = argparse.ArgumentParser(prog='bindgen', description='ImGui Binding Generator')
parser.add_argument('imgui_dir', help='path to imgui directory')
parser.add_argument('-o', '--out', default='pybind11_imgui', help='basename of output file')
args = parser.parse_args()

outname = args.out

header_template = '''
// Auto generated pybind11 binding for imgui
#pragma once
#include <pybind11/pybind11.h>

void bind_imgui_to_py(pybind11::module& m);
'''
with open(outname+'.h', 'w') as h:
    h.write(header_template)

#-----------------------------------------

with open(os.path.join(args.imgui_dir,'imgui.h')) as imgui_h:
    imgui_h_content = imgui_h.read()

class ImGuiEnum(object):
    pyname:str
    cppname:str
    fields:list[tuple[str,str,str]]

    def __init__(self):
        self.pyname = ''
        self.cppname = ''
        self.fields = []

class ImGuiApi(object):
    name:str
    rettype:str
    signature:str
    argtypes:list[str]
    argdefaults:list[str]
    supported:bool
    #arg_re = re.compile(r'^([\w\s*&]+)\s+(\w+)(\[\d*\])?\s*(=\s*([\w\de+-.%" ]+))?$')
    arg_re = re.compile(r'^([\w\s*&]+)\s+(\w+)(\[\d*\])?\s*(=\s*(.+))?$')

    def __init__(self):
        self.name = ''
        self.doc = ''
        self.rettype = ''
        self.signature = ''
        self.argtypes = []
        self.argnames = []
        self.argdefaults = []
        self.supported = True

    def setSignature(self, signature):
        self.signature = signature
        args = []
        if signature.strip() == '':
            return
        elif ',' not in signature:
            args = [signature]
        else:
            # args = signature.split(',')  # this can't handle default args with constructor, e.g., size = ImVec2(0,0)
            word = ''
            par = 0 # unbalanced parenthesis
            for c in signature:
                if c == '(':
                    par += 1
                if c == ')':
                    par -= 1
                if c == ',' and par == 0:
                    args.append(word.strip())
                    word = ''
                    continue
                word += c
            args.append(word)
        for arg in args:
            m = self.arg_re.match(arg)
            if m:
                self.argtypes.append(m.group(1).strip())
                self.argnames.append(m.group(2).strip())
                self.argdefaults.append(m.group(5))
                t = m.group(1).strip()
                if ('*' in t and 'char' not in t) or \
                   ('&' in t and 'const' not in t):
                    self.supported = False
                    print(f'unsupported arg for {self.name}: {arg}')
            else:
                print(f'unsupported arg for {self.name}: {arg}')
                self.supported = False
        #print(f'{self.name}: types: {self.argtypes}; names: {self.argnames}; defaults: {self.argdefaults}')

    def pyarg(self):
        if len(self.argnames) == 0:
            return ''
        parts = []
        for i in range(len(self.argnames)):
            part = f'py::arg("{self.argnames[i]}")'
            if self.argdefaults[i] is not None:
                part += f' = {self.argdefaults[i]}'
            parts.append(part)
        return ', '+(', '.join(parts))

    def docarg(self):
        if self.doc:
            doc = self.doc.replace('"', '\\"')
            return f', "{doc}"'
        else:
            return ''

imgui_enums = []
imgui_api_list = []

in_enum = False
in_imgui_namespace = False
enum_start = re.compile(r'^enum\s+(ImGui(\w+)_)$')
enum_field = re.compile(r'^\s*(ImGui\w+_(\w+))\s*(=?.*?,?\s*)(//\s*(.+))?$')
enum_end = re.compile(r'^\s*}\s*;\s*$')

#api = re.compile(r'^\s*IMGUI_API\s+((const\s+)?\w+\s*\*?)\s+(\w+)\(([^;]*)\)\s*(IM_FMTARGS\(\d\)|IM_FMTLIST)?\s*;\s*(//\s*(.+))?$')
api_start = re.compile(r'^\s*IMGUI_API\s+((const\s+)?\w+\s*\*?)\s+(\w+)\(')
def parseAPI(line):
    m = api_start.match(line)
    if not m:
        return
    ret, name = m.group(1), m.group(3)
    rest = line[m.span()[1]:]
    #print(rest)
    par = 1 # unbalanced parenthesis
    sig = ''
    for c in rest:
        if c == '(':
            par+=1
        if c == ')':
            par-=1
            if par == 0:
                break
        sig += c
    rest = rest[len(sig)+1:]
    commentstart = rest.find('//')
    doc = None
    if commentstart != -1:
        doc = rest[commentstart+2:].strip()
    return ret.strip(), name, sig, doc

brace_in_namespace = 0
for line in imgui_h_content.split('\n'):
    if not in_enum:
        m = enum_start.match(line)
        if m:
            e = ImGuiEnum()
            e.pyname = m.group(2)
            e.cppname = m.group(1)
            imgui_enums.append(e)
            in_enum = True
    if in_enum:
        m = enum_field.match(line)
        if m:
            name = m.group(2) if m.group(2)!='None' else 'NONE'
            if name.lower() == 'count':
                continue
            imgui_enums[-1].fields.append((name, m.group(1), m.group(5)))
        elif enum_end.match(line):
            in_enum = False

    if not in_enum and not in_imgui_namespace:
        if line.strip()=='namespace ImGui':
            in_imgui_namespace = True
            brace_in_namespace = 0
            continue
    if in_imgui_namespace:
        if line.strip() == '':
            continue
        brace_in_namespace += line.count('{')
        brace_in_namespace -= line.count('}')
        if brace_in_namespace <= 0:
            in_imgui_namespace = False
    if in_imgui_namespace:
        m = parseAPI(line)
        if m:
            f = ImGuiApi()
            f.rettype = m[0]
            f.name = m[1]
            f.setSignature(m[2])
            f.doc = m[3]
            #print(f'{f.name}: <{f.signature}>')
            imgui_api_list.append(f)

imgui_api_map = {}
for api in imgui_api_list:
    if api.name not in imgui_api_map:
        imgui_api_map[api.name] = set()
    imgui_api_map[api.name].add(api)

# [] are skip marks, those functions should be implemented manually
export_api_list = '''
[Begin] End BeginChild EndChild
IsWindowAppearing IsWindowCollapsed IsWindowFocused IsWindowHovered GetWindowPos GetWindowSize GetWindowWidth GetWindowHeight
SetNextWindowPos SetNextWindowSize SetNextWindowContentSize SetNextWindowCollapsed SetNextWindowFocus SetNextWindowBgAlpha
SetWindowPos SetWindowSize SetWindowCollapsed SetWindowFocus SetWindowFontScale
GetContentRegionAvail GetContentRegionMax
GetWindowContentRegionMin GetWindowContentRegionMax
GetScrollX GetScrollY SetScrollX SetScrollY GetScrollMaxX GetScrollMaxY SetScrollHereX SetScrollHereY SetScrollFromPosX SetScrollFromPosY
PushStyleColor PopStyleColor PushStyleVar PopStyleVar
PushTabStop PopTabStop PushButtonRepeat PopButtonRepeat
PushItemWidth PopItemWidth SetNextItemWidth CalcItemWidth PushTextWrapPos PopTextWrapPos

Separator SameLine NewLine Spacing Dummy Indent Unindent BeginGroup EndGroup
GetCursorPos GetCursorPosX GetCursorPosY SetCursorPos SetCursorPosX SetCursorPosY
GetCursorStartPos GetCursorScreenPos SetCursorScreenPos
AlignTextToFramePadding GetTextLineHeight GetTextLineHeightWithSpacing GetFrameHeight GetFrameHeightWithSpacing

[PushID] PopID [GetID]

[Text]
Button SmallButton InvisibleButton ArrowButton
[Checkbox] RadioButton ProgressBar Bullet

BeginCombo EndCombo BeginListBox EndListBox
TreeNode TreePush TreePop GetTreeNodeToLabelSpacing CollapsingHeader SetNextItemOpen Selectable

GetMainViewport
BeginMenuBar EndMenuBar BeginMainMenuBar EndMainMenuBar BeginMenu EndMenu MenuItem
BeginTooltip EndTooltip BeginItemTooltip
[SetTooltip] [SetItemTooltip]
BeginPopup [BeginPopupModal] EndPopup OpenPopup OpenPopupOnItemClick CloseCurrentPopup
BeginPopupContextItem BeginPopupContextWindow BeginPopupContextVoid IsPopupOpen

BeginTable EndTable TableNextRow TableNextColumn TableSetColumnIndex
TableSetupColumn TableSetupScrollFreeze TableHeadersRow TableHeader
TableGetColumnCount TableGetColumnIndex TableGetRowIndex TableGetColumnName TableGetColumnFlags TableSetColumnEnabled TableSetBgColor

BeginTabBar EndTabBar [BeginTabItem] EndTabItem TabItemButton SetTabItemClosed
BeginDisabled EndDisabled

SetItemDefaultFocus SetKeyboardFocusHere SetNextItemAllowOverlap
IsItemHovered IsItemActive IsItemFocused IsItemClicked IsItemVisible IsItemEdited IsItemActivated IsItemDeactivated IsItemDeactivatedAfterEdit
IsItemToggledOpen IsAnyItemHovered IsAnyItemActive IsAnyItemFocused GetItemID GetItemRectMin GetItemRectMax GetItemRectSize IsRectVisible

BeginChildFrame EndChildFrame

IsKeyDown IsKeyPressed IsKeyReleased SetNextFrameWantCaptureKeyboard
IsMouseDown IsMouseClicked IsMouseReleased IsMouseDoubleClicked IsMouseHoveringRect IsAnyMouseDown GetMousePos GetMousePosOnOpeningCurrentPopup
IsMouseDragging GetMouseDragDelta ResetMouseDragDelta GetMouseCursor SetMouseCursor SetNextFrameWantCaptureMouse

GetClipboardText SetClipboardText
'''

manual_impl_pre = r'''
  py::class_<ImVec2>(m, "ImVec2")
    .def(py::init<>())
    .def(py::init<float, float>())
    .def_readwrite("x", &ImVec2::x)
    .def_readwrite("y", &ImVec2::y);

  py::class_<ImVec4>(m, "ImVec4")
    .def(py::init<>())
    .def(py::init<float, float, float, float>())
    .def_readwrite("x", &ImVec4::x)
    .def_readwrite("y", &ImVec4::y)
    .def_readwrite("z", &ImVec4::z)
    .def_readwrite("w", &ImVec4::w);

  py::class_<ImGuiListClipper>(m, "ListClipper")
    .def(py::init<>())
    .def_readonly("DisplayStart", &ImGuiListClipper::DisplayStart, "First item to display, updated by each call to Step()")
    .def_readonly("DisplayEnd", &ImGuiListClipper::DisplayEnd, "End of items to display (exclusive)")
    .def("Begin", &ImGuiListClipper::Begin, py::arg("items_count"), py::arg("items_height") = -1.0f, "items_count: Use INT_MAX if you don't know how many items you have (in which case the cursor won't be advanced in the final step)\\nitems_height: Use -1.0f to be calculated automatically on first step. Otherwise pass in the distance between your items, typically GetTextLineHeightWithSpacing() or GetFrameHeightWithSpacing().")
    .def("End", &ImGuiListClipper::End, "Automatically called on the last call of Step() that returns false.")
    .def("Step", &ImGuiListClipper::Step, "Call until it returns false. The DisplayStart/DisplayEnd fields will be set and you can process/draw those items.");

  py::class_<ImGuiViewport>(m, "Viewport")
    .def_readonly("Flags", &ImGuiViewport::Flags)
    .def_readonly("Pos", &ImGuiViewport::Pos)
    .def_readonly("Size", &ImGuiViewport::Size)
    .def_readonly("WorkPos", &ImGuiViewport::WorkPos)
    .def_readonly("WorkSize", &ImGuiViewport::WorkSize);

'''

manual_impl_post = r'''

  m.def("Begin", [](char const* name, bool open, ImGuiWindowFlags flags)->py::tuple {
    bool shown = ImGui::Begin(name, &open, flags);
    return py::make_tuple(shown, open);
  }, py::arg("name"), py::arg("open") = true, py::arg("flags") = 0);
  m.def("BeginTable", [](const char* str_id, int column, ImGuiTableFlags flags, ImVec2 outer_size, float inner_width){
    bool ret = ImGui::BeginTable(str_id, column, flags, outer_size, inner_width);
    return py::make_tuple(ret, outer_size);
  }, py::arg("str_id"), py::arg("column"), py::arg("flags")=0, py::arg("outer_size")=ImVec2(0,0), py::arg("inner_width")=0.f);
  m.def("PushID", py::overload_cast<char const*>(&ImGui::PushID), py::arg("str_id"));
  m.def("PushID", py::overload_cast<int>(&ImGui::PushID), py::arg("int_id"));
  m.def("GetID",  py::overload_cast<char const*>(&ImGui::GetID), py::arg("str_id"));
  m.def("BeginPopupModal", [](char const* name, bool open, ImGuiWindowFlags flags)->py::tuple {
    bool shown = ImGui::BeginPopupModal(name, &open, flags);
    return py::make_tuple(shown, open);
  }, py::arg("name"), py::arg("open") = true, py::arg("flags") = 0);
  m.def("Text", [](std::string_view str){
    ImGui::TextUnformatted(&*str.begin(), &*str.end());
  }, py::arg("text"));
  m.def("InputText", [](char const* label, std::string str, ImGuiInputTextFlags flags) {
    bool mod = ImGui::InputText(label, &str, flags);
    return py::make_tuple(mod, str);
  }, py::arg("label"), py::arg("text"), py::arg("flags") = 0);
  m.def("InputTextMultiline", [](char const* label, std::string str, ImVec2 const& size, ImGuiInputTextFlags flags) {
    bool mod = ImGui::InputTextMultiline(label, &str, size, flags);
    return py::make_tuple(mod, str);
  }, py::arg("label"), py::arg("text"), py::arg("size") = ImVec2(0,0), py::arg("flags") = 0);
  m.def("Checkbox", [](char const* label, bool checked) {
    bool mod = ImGui::Checkbox(label, &checked);
    return py::make_tuple(mod, checked);
  }, py::arg("label"), py::arg("checked"));
  m.def("BeginTabItem", [](char const* label, bool open, ImGuiTabItemFlags flags){
    bool shown = ImGui::BeginTabItem(label, &open, flags);
    return py::make_tuple(shown, open);
  }, py::arg("name"), py::arg("open") = true, py::arg("flags") = 0);
  m.def("SetTooltip", [](char const* tip){
    ImGui::SetTooltip("%s", tip);
  }, py::arg("tooltip"));
  m.def("SetItemTooltip", [](char const* tip){
    ImGui::SetItemTooltip("%s", tip);
  }, py::arg("tooltip"));
  
  m.def("DragScalar", [](char const* label, ImGuiDataType type, py::object value, float speed, py::object vmin, py::object vmax, char const* format, ImGuiSliderFlags flags){
    int8_t   i8[4]  = {0}, i8minmax[2];
    uint8_t  u8[4]  = {0}, u8minmax[2];
    int16_t  i16[4] = {0}, i16minmax[2];
    uint16_t u16[4] = {0}, u16minmax[2];
    int32_t  i32[4] = {0}, i32minmax[2];
    uint32_t u32[4] = {0}, u32minmax[2];
    int64_t  i64[4] = {0}, i64minmax[2];
    uint64_t u64[4] = {0}, u64minmax[2];
    float    f32[4] = {0}, f32minmax[2];
    double   f64[4] = {0}, f64minmax[2];
    void     *pdata = nullptr;
    void      *pmin = nullptr, *pmax = nullptr;
    int     numcomp = 1;

#define TYPE_CASE(X, Y, T) \
        case ImGuiDataType_##X:\
          pdata = Y; Y[comp] = py::cast<T>(val);\
          if (!pmin && vmin) { Y##minmax[0] = py::cast<T>(vmin); pmin = Y##minmax; }\
          if (!pmax && vmax) { Y##minmax[1] = py::cast<T>(vmax); pmax = Y##minmax+1; }\
          break
    auto assign = [&](int comp, py::handle val) {
      switch(type) {
        TYPE_CASE(S8, i8, int8_t);
        TYPE_CASE(U8, u8, uint8_t);
        TYPE_CASE(S16, i16, int16_t);
        TYPE_CASE(U16, u16, uint16_t);
        TYPE_CASE(S32, i32, int32_t);
        TYPE_CASE(U32, u32, uint32_t);
        TYPE_CASE(S64, i64, int64_t);
        TYPE_CASE(U64, u64, uint64_t);
        TYPE_CASE(Float, f32, float);
        TYPE_CASE(Double, f64, double);
        default:
          throw std::runtime_error("unsupported type for DragScalar");
      }
    };
#undef TYPE_CASE
    if (py::isinstance<py::tuple>(value)) {
      py::tuple tp = value;
      numcomp = tp.size();
      if (numcomp < 1 || numcomp > 4)
        throw std::range_error("number of component not in range [1,4]");
      for (int i=0; i<numcomp; ++i)
        assign(i, tp[i]);
    } else {
      assign(0, value);
    }

    if (format && format[0]==0) format = nullptr;
    bool mod = ImGui::DragScalarN(label, type, pdata, numcomp, speed, pmin, pmax, format, flags);

    py::tuple retval(numcomp);
    for (int i=0; i<numcomp; ++i) {
      switch(type) {
        case ImGuiDataType_S8:
          retval[i] = i8[i]; break;
        case ImGuiDataType_U8:
          retval[i] = u8[i]; break;
        case ImGuiDataType_S16:
          retval[i] = i16[i]; break;
        case ImGuiDataType_U16:
          retval[i] = u16[i]; break;
        case ImGuiDataType_S32:
          retval[i] = i32[i]; break;
        case ImGuiDataType_U32:
          retval[i] = u32[i]; break;
        case ImGuiDataType_S64:
          retval[i] = i64[i]; break;
        case ImGuiDataType_U64:
          retval[i] = u64[i]; break;
        case ImGuiDataType_Float:
          retval[i] = f32[i]; break;
        case ImGuiDataType_Double:
          retval[i] = f64[i]; break;
        default:
          throw std::runtime_error("unsupported type for DragScalar");
      }
    }
    if (py::isinstance<py::tuple>(value))
      return py::make_tuple(mod, retval);
    else
      return py::make_tuple(mod, retval[0]);
  }, py::arg("label"), py::arg("type"), py::arg("value"), py::arg("speed")=1.f, py::arg("min")=py::none(), py::arg("max")=py::none(), py::arg("format")="", py::arg("flags")=0);

  m.def("SliderScalar", [](char const* label, ImGuiDataType type, py::object value, py::object vmin, py::object vmax, char const* format, ImGuiSliderFlags flags){
    int8_t   i8[4]  = {0}, i8minmax[2];
    uint8_t  u8[4]  = {0}, u8minmax[2];
    int16_t  i16[4] = {0}, i16minmax[2];
    uint16_t u16[4] = {0}, u16minmax[2];
    int32_t  i32[4] = {0}, i32minmax[2];
    uint32_t u32[4] = {0}, u32minmax[2];
    int64_t  i64[4] = {0}, i64minmax[2];
    uint64_t u64[4] = {0}, u64minmax[2];
    float    f32[4] = {0}, f32minmax[2];
    double   f64[4] = {0}, f64minmax[2];
    void     *pdata = nullptr;
    void      *pmin = nullptr, *pmax = nullptr;
    int     numcomp = 1;

#define TYPE_CASE(X, Y, T) \
        case ImGuiDataType_##X:\
          pdata = Y; Y[comp] = py::cast<T>(val);\
          if (!pmin && vmin) { Y##minmax[0] = py::cast<T>(vmin); pmin = Y##minmax; }\
          if (!pmax && vmax) { Y##minmax[1] = py::cast<T>(vmax); pmax = Y##minmax+1; }\
          break
    auto assign = [&](int comp, py::handle val) {
      switch(type) {
        TYPE_CASE(S8, i8, int8_t);
        TYPE_CASE(U8, u8, uint8_t);
        TYPE_CASE(S16, i16, int16_t);
        TYPE_CASE(U16, u16, uint16_t);
        TYPE_CASE(S32, i32, int32_t);
        TYPE_CASE(U32, u32, uint32_t);
        TYPE_CASE(S64, i64, int64_t);
        TYPE_CASE(U64, u64, uint64_t);
        TYPE_CASE(Float, f32, float);
        TYPE_CASE(Double, f64, double);
        default:
          throw std::runtime_error("unsupported type for DragScalar");
      }
    };
#undef TYPE_CASE
    if (py::isinstance<py::tuple>(value)) {
      py::tuple tp = value;
      numcomp = tp.size();
      if (numcomp < 1 || numcomp > 4)
        throw std::range_error("number of component not in range [1,4]");
      for (int i=0; i<numcomp; ++i)
        assign(i, tp[i]);
    } else {
      assign(0, value);
    }

    bool mod = ImGui::SliderScalarN(label, type, pdata, numcomp, pmin, pmax, format, flags);

    py::tuple retval(numcomp);
    for (int i=0; i<numcomp; ++i) {
      switch(type) {
        case ImGuiDataType_S8:
          retval[i] = i8[i]; break;
        case ImGuiDataType_U8:
          retval[i] = u8[i]; break;
        case ImGuiDataType_S16:
          retval[i] = i16[i]; break;
        case ImGuiDataType_U16:
          retval[i] = u16[i]; break;
        case ImGuiDataType_S32:
          retval[i] = i32[i]; break;
        case ImGuiDataType_U32:
          retval[i] = u32[i]; break;
        case ImGuiDataType_S64:
          retval[i] = i64[i]; break;
        case ImGuiDataType_U64:
          retval[i] = u64[i]; break;
        case ImGuiDataType_Float:
          retval[i] = f32[i]; break;
        case ImGuiDataType_Double:
          retval[i] = f64[i]; break;
        default:
          throw std::runtime_error("unsupported type for SliderScalar");
      }
    }
    if (py::isinstance<py::tuple>(value))
      return py::make_tuple(mod, retval);
    else
      return py::make_tuple(mod, retval[0]);
  }, py::arg("label"), py::arg("type"), py::arg("value"), py::arg("min")=0, py::arg("max")=10, py::arg("format")="%.3f", py::arg("flags")=0);

  // TODO: VSliderScalar, InputScalarN, ColorEdit3, ColorEdit4, ColorPicker3, ColorPicker3, ColorButton
'''

#-----------------------------------------

cpp_src = f'''
#include "{outname}.h"
#include <imgui.h>
#include <imgui_stdlib.h>

namespace py = pybind11;

void bind_imgui_to_py(py::module& m)
{{
'''

cpp_src += manual_impl_pre

for e in imgui_enums:
    cpp_src += f'  py::enum_<{e.cppname}>(m, "{e.pyname}", py::arithmetic())\n'
    for f in e.fields:
        doc = f[2]
        if doc:
            docstr = ', "'+doc.replace('"', '\\"')+'"'
        else:
            docstr = ''
        cpp_src += f'    .value("{f[0]}", {f[1]}{docstr})\n'
    cpp_src += '  ;\n\n'

for name in filter(lambda x: x!='', itertools.chain.from_iterable(map(lambda x:x.split(), export_api_list.split('\n')))):
    if name[0] == '[': # manual-implement mark
        continue
    if name in imgui_api_map:
        variants = imgui_api_map[name]
        if len(variants) == 1:
            v = [i for i in variants][0]
            if not v.supported:
                print(f'API {name} is not supported')
                continue
            cpp_src += f'  m.def("{name}", &ImGui::{name}{v.pyarg()}{v.docarg()});\n'
        else:
            hasSupportedVariant = False
            for v in variants:
                if v.supported:
                    hasSupportedVariant = True
                    cpp_src += f'  m.def("{name}", py::overload_cast<{", ".join(v.argtypes)}>(&ImGui::{name}){v.pyarg()}{v.docarg()});\n'
            if not hasSupportedVariant:
                print(f'API {name} is not supported')
    else:
        print(f'declare of function "{name}" cannot be found')

cpp_src += manual_impl_post
cpp_src += '\n}\n'


with open(outname+'.cpp', 'w') as cpp:
    cpp.write(cpp_src)

