#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para criar modelos 3D de exemplo para o sistema Hyper3D + Blender.
Este script cria exemplos válidos no modo de simulação.
"""

import os
import sys
import argparse
import subprocess
import shutil
import tempfile

def find_blender():
    """Encontra o executável do Blender no sistema."""
    # Procurar nos caminhos comuns
    blender_path = shutil.which("blender")
    if not blender_path:
        # Tentar caminhos comuns no macOS
        common_paths = [
            "/Applications/Blender.app/Contents/MacOS/Blender",
            "/usr/local/bin/blender",
            "/opt/homebrew/bin/blender"
        ]
        for path in common_paths:
            if os.path.exists(path):
                blender_path = path
                break
    
    if not blender_path:
        raise FileNotFoundError("Blender não encontrado. Por favor, instale o Blender ou adicione-o ao PATH.")
    
    return blender_path

def create_example_model(output_path, shape="cube"):
    """
    Cria um modelo 3D de exemplo usando Blender.
    
    Args:
        output_path: Caminho para salvar o modelo
        shape: Forma do modelo (cube, sphere, etc.)
    """
    # Garantir que o diretório de saída exista
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Criar script temporário para Blender
    with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as temp:
        script_path = temp.name
        
        # Escrever script Python para Blender
        script = f"""
import bpy
import os

# Limpar cena
bpy.ops.wm.read_factory_settings(use_empty=True)

# Remover objetos padrão
for obj in bpy.context.scene.objects:
    bpy.data.objects.remove(obj, do_unlink=True)

# Criar objeto
if "{shape}" == "cube":
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))
elif "{shape}" == "sphere":
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, location=(0, 0, 0))
elif "{shape}" == "monkey":
    bpy.ops.mesh.primitive_monkey_add(size=2, location=(0, 0, 0))
else:
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))

# Adicionar material
mat = bpy.data.materials.new(name="Material")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs[0].default_value = (0.8, 0.2, 0.2, 1.0)  # Cor vermelha
bsdf.inputs[7].default_value = 0.2  # Metallic
bsdf.inputs[9].default_value = 0.8  # Roughness

# Aplicar material ao objeto
obj = bpy.context.object
if obj.data.materials:
    obj.data.materials[0] = mat
else:
    obj.data.materials.append(mat)

# Rotacionar um pouco o objeto para parecer mais interessante
obj.rotation_euler = (0.3, 0.2, 0.1)

# Garantir que o diretório de saída exista
output_dir = os.path.dirname("{output_path}")
os.makedirs(output_dir, exist_ok=True)

# Exportar como GLB
bpy.ops.export_scene.gltf(
    filepath="{output_path}",
    export_format='GLB',
    use_selection=False,
    export_animations=True
)

print(f"Modelo exportado para: {output_path}")
"""
        
        # Escrever script no arquivo temporário
        temp.write(script.encode('utf-8'))
    
    # Encontrar o executável do Blender
    blender_path = find_blender()
    
    # Executar Blender com o script
    blender_command = [blender_path, "--background", "--python", script_path]
    
    print(f"Executando: {' '.join(blender_command)}")
    
    result = subprocess.run(
        blender_command,
        capture_output=True,
        text=True,
        check=False
    )
    
    # Remover script temporário
    os.unlink(script_path)
    
    # Verificar resultado
    if result.returncode != 0:
        print(f"Erro ao executar Blender: {result.stderr}")
        return False
    
    # Verificar se o arquivo foi criado
    if os.path.exists(output_path):
        print(f"Modelo criado com sucesso: {output_path}")
        return True
    else:
        print(f"Erro: Arquivo não foi criado: {output_path}")
        return False

def main():
    """Função principal."""
    parser = argparse.ArgumentParser(description="Cria modelos 3D de exemplo para o sistema Hyper3D + Blender")
    parser.add_argument("--output", default="example_models/example_cube.glb", help="Caminho para salvar o modelo")
    parser.add_argument("--shape", default="cube", choices=["cube", "sphere", "monkey"], help="Forma do modelo")
    
    args = parser.parse_args()
    
    # Tornar o caminho absoluto se não for
    if not os.path.isabs(args.output):
        args.output = os.path.join(os.getcwd(), args.output)
    
    # Criar modelo
    success = create_example_model(args.output, args.shape)
    
    # Copiar para o cache se for bem-sucedido
    if success:
        # Caminhos de cache específicos do problema
        cache_paths = [
            "hyper3d_cache/57bc61bed665be604f63fe34e46d7a0f_model.glb",
            "hyper3d_cache/16415f5d7966226bbd7ab0ef83d7c8a3_model.glb"
        ]
        
        for cache_path in cache_paths:
            if not os.path.isabs(cache_path):
                cache_path = os.path.join(os.getcwd(), cache_path)
            
            # Criar diretório se necessário
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            
            # Copiar o modelo para o cache
            shutil.copy2(args.output, cache_path)
            print(f"Modelo copiado para o cache: {cache_path}")

if __name__ == "__main__":
    main()
