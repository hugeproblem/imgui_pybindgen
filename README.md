A simple ImGui binding generator
=================================

Call `bind_imgui_to_py(pybind11::module& m);` and you can use ImGui in python

Available APIs are - 

```
Begin End BeginChild EndChild
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

PushID PopID GetID

Text
Button SmallButton InvisibleButton ArrowButton
Checkbox RadioButton ProgressBar Bullet

BeginCombo EndCombo BeginListBox EndListBox
TreeNode TreePush TreePop GetTreeNodeToLabelSpacing CollapsingHeader SetNextItemOpen Selectable
*SliderScalar *DragScalar

GetMainViewport
BeginMenuBar EndMenuBar BeginMainMenuBar EndMainMenuBar BeginMenu EndMenu MenuItem
BeginTooltip EndTooltip BeginItemTooltip
SetTooltip SetItemTooltip
BeginPopup BeginPopupModal EndPopup OpenPopup OpenPopupOnItemClick CloseCurrentPopup
BeginPopupContextItem BeginPopupContextWindow BeginPopupContextVoid IsPopupOpen

BeginTable EndTable TableNextRow TableNextColumn TableSetColumnIndex
TableSetupColumn TableSetupScrollFreeze TableHeadersRow TableHeader
TableGetColumnCount TableGetColumnIndex TableGetRowIndex TableGetColumnName TableGetColumnFlags TableSetColumnEnabled TableSetBgColor

BeginTabBar EndTabBar BeginTabItem EndTabItem TabItemButton SetTabItemClosed
BeginDisabled EndDisabled

SetItemDefaultFocus SetKeyboardFocusHere SetNextItemAllowOverlap
IsItemHovered IsItemActive IsItemFocused IsItemClicked IsItemVisible IsItemEdited IsItemActivated IsItemDeactivated IsItemDeactivatedAfterEdit
IsItemToggledOpen IsAnyItemHovered IsAnyItemActive IsAnyItemFocused GetItemID GetItemRectMin GetItemRectMax GetItemRectSize IsRectVisible

BeginChildFrame EndChildFrame

IsKeyDown IsKeyPressed IsKeyReleased SetNextFrameWantCaptureKeyboard
IsMouseDown IsMouseClicked IsMouseReleased IsMouseDoubleClicked IsMouseHoveringRect IsAnyMouseDown GetMousePos GetMousePosOnOpeningCurrentPopup
IsMouseDragging GetMouseDragDelta ResetMouseDragDelta GetMouseCursor SetMouseCursor SetNextFrameWantCaptureMouse

GetClipboardText SetClipboardText
```

*\* SliderScalar and DragScalar is hand-writen for python and it can handle tuples with SliderScalarN and DragScalarN*

Flags are translated in such pattern: `ImGuiSelectableFlags_AllowOverlap` &rArr; `ImGui.SelectableFlags.AllowOverlap`

APIs with read-write pointer argument are translated in such pattern: `bool Checkbox(label, bool* checked)` &rArr; `Checkbox(label, checked) -> tuple(value_modified, new_checked_value)`

In case of API signature has changed or flags has changed, call `python bindgen.py /path/to/imgui/` to re-generate the binding

-----

I made this to fit my own need. 

In my situation, I have a native app made with ImGui, and I want to expose
*just enough* ImGui API to python, not the entire ImGui world,
its internals, the windowing, the backends and everything.

And I want it compiled within my own module, so that my native code and
python extension can share a static ImGui library.

I find it surprisingly hard to fit my needs with existing python bindings,
and it's surprisingly easy to do it myself

-- so, here it is.

