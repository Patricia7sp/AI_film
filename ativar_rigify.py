import bpy

# Ativa o Rigify
bpy.ops.preferences.addon_enable(module="rigify")

# Salva as preferências para manter o Rigify ativado nas próximas execuções
bpy.ops.wm.save_userpref()
