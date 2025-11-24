"""
LangGraph Adapter for Open3D Implementation
Integrates LangGraph workflows with Open3D visualization
"""

from typing import Dict, Any, TypedDict, List
from dataclasses import dataclass


class Open3DAgentState(TypedDict):
    """State for Open3D Agent workflow"""
    messages: List[str]
    current_step: str
    scene_data: Dict[str, Any]
    generated_content: Dict[str, Any]


def create_open3d_workflow():
    """
    Creates a LangGraph workflow for Open3D processing
    
    Returns:
        A configured LangGraph workflow
    """
    try:
        from langgraph.graph import StateGraph, END
        from orchestration.llm_config import get_llm, generate_cinematic_prompt
        import json
        import os
        
        print("🔧 Criando workflow LangGraph funcional...")
        
        def extract_story(state: Open3DAgentState) -> Open3DAgentState:
            """Extract and process story from multimodal input"""
            story_text = state.get('story_text', '')
            
            if not story_text:
                # Try to get from enhanced_multimodal_input_asset
                if 'enhanced_multimodal_input_asset' in state:
                    story_text = state['enhanced_multimodal_input_asset'].get('story_text', '')
            
            print(f"📖 Processando história: {len(story_text)} caracteres")
            
            # Generate cinematic prompt
            llm = get_llm()
            prompt = generate_cinematic_prompt(story_text)
            
            state.update({
                'story_text': story_text,
                'cinematic_prompt': prompt,
                'current_step': 'story_extracted'
            })
            
            return state
        
        def generate_scenes(state: Open3DAgentState) -> Open3DAgentState:
            """Generate scenes from story"""
            story_text = state.get('story_text', '')
            cinematic_prompt = state.get('cinematic_prompt', '')
            
            print("🎬 Gerando cenas...")
            
            # Simple scene generation (placeholder)
            scenes = [
                {
                    "scene_id": 1,
                    "description": f"Opening scene: {story_text[:100]}...",
                    "prompt": cinematic_prompt,
                    "duration": 5
                },
                {
                    "scene_id": 2,
                    "description": f"Development: Based on {story_text[:50]}...",
                    "prompt": cinematic_prompt,
                    "duration": 7
                },
                {
                    "scene_id": 3,
                    "description": f"Climax: {story_text[:80]}...",
                    "prompt": cinematic_prompt,
                    "duration": 6
                }
            ]
            
            state.update({
                'scenes': scenes,
                'scenes_count': len(scenes),
                'current_step': 'scenes_generated'
            })
            
            print(f"✅ {len(scenes)} cenas geradas")
            return state
        
        def generate_images(state: Open3DAgentState) -> Open3DAgentState:
            """Generate images for scenes using ComfyUI"""
            scenes = state.get('scenes', [])
            comfyui_url = os.getenv('COMFYUI_URL', '')
            
            print("🖼️ Gerando imagens com ComfyUI...")
            
            scene_images = []
            
            for i, scene in enumerate(scenes[:3]):  # Limit to 3 scenes
                try:
                    print(f"🎨 Gerando imagem para cena {scene['scene_id']}...")
                    
                    # Create output directory
                    os.makedirs('output', exist_ok=True)
                    image_path = f"output/scene_{scene['scene_id']}_image.png"
                    
                    # Generate image using ComfyUI
                    if comfyui_url:
                        import requests
                        import json
                        import time
                        import base64
                        from PIL import Image
                        import io
                        
                        # ComfyUI workflow for image generation
                        workflow = {
                            "1": {
                                "inputs": {
                                    "text": scene['prompt'],
                                    "clip": ["4", 1]
                                },
                                "class_type": "CLIPTextEncode"
                            },
                            "2": {
                                "inputs": {
                                    "text": "",
                                    "clip": ["4", 1]
                                },
                                "class_type": "CLIPTextEncode"
                            },
                            "3": {
                                "inputs": {
                                    "seed": 123456789,
                                    "steps": 20,
                                    "cfg": 8,
                                    "sampler_name": "euler",
                                    "scheduler": "normal",
                                    "denoise": 1,
                                    "model": ["4", 0],
                                    "positive": ["1", 0],
                                    "negative": ["2", 0],
                                    "latent_image": ["5", 0]
                                },
                                "class_type": "KSampler"
                            },
                            "4": {
                                "inputs": {
                                    "ckpt_name": "v1-5-pruned-emaonly.safetensors"
                                },
                                "class_type": "CheckpointLoaderSimple"
                            },
                            "5": {
                                "inputs": {
                                    "width": 512,
                                    "height": 512,
                                    "batch_size": 1
                                },
                                "class_type": "EmptyLatentImage"
                            },
                            "6": {
                                "inputs": {
                                    "samples": ["3", 0],
                                    "vae": ["4", 2]
                                },
                                "class_type": "VAEDecode"
                            },
                            "7": {
                                "inputs": {
                                    "filename_prefix": f"scene_{scene['scene_id']}",
                                    "images": ["6", 0]
                                },
                                "class_type": "SaveImage"
                            }
                        }
                        
                        # Submit workflow to ComfyUI
                        response = requests.post(f"{comfyui_url}/prompt", json={"prompt": workflow})
                        
                        if response.status_code == 200:
                            result = response.json()
                            prompt_id = result.get('prompt_id')
                            
                            if prompt_id:
                                # Wait for completion and get image
                                time.sleep(10)  # Wait for generation
                                
                                # Get generated image
                                history_response = requests.get(f"{comfyui_url}/history/{prompt_id}")
                                if history_response.status_code == 200:
                                    history = history_response.json()
                                    outputs = history.get(prompt_id, {}).get('outputs', {})
                                    
                                    if '7' in outputs:
                                        images = outputs['7']['images']
                                        if images:
                                            # Download image
                                            image_data = images[0]
                                            image_response = requests.get(f"{comfyui_url}/view?filename={image_data['filename']}")
                                            
                                            if image_response.status_code == 200:
                                                # Save image
                                                with open(image_path, 'wb') as f:
                                                    f.write(image_response.content)
                                                
                                                scene_images.append({
                                                    'scene_id': scene['scene_id'],
                                                    'image_path': image_path,
                                                    'prompt': scene['prompt'],
                                                    'comfyui_prompt_id': prompt_id
                                                })
                                                
                                                print(f"✅ Imagem ComfyUI gerada: cena {scene['scene_id']}")
                                                continue
                            
                            # Fallback to mock if ComfyUI fails
                            print(f"⚠️ ComfyUI falhou, usando mock para cena {scene['scene_id']}")
                    
                    # Fallback mock generation
                    with open(image_path, 'w') as f:
                        f.write(f"Mock image for scene {scene['scene_id']}: {scene['prompt']}")
                    
                    scene_images.append({
                        'scene_id': scene['scene_id'],
                        'image_path': image_path,
                        'prompt': scene['prompt'],
                        'generation_method': 'mock'
                    })
                    
                    print(f"✅ Imagem gerada (mock): cena {scene['scene_id']}")
                    
                except Exception as e:
                    print(f"⚠️ Erro ao gerar imagem para cena {scene['scene_id']}: {e}")
                    # Continue with next scene
            
            state.update({
                'scene_images': scene_images,
                'images_count': len(scene_images),
                'current_step': 'images_generated'
            })
            
            return state
        
        def generate_audio(state: Open3DAgentState) -> Open3DAgentState:
            """Generate audio narration using ElevenLabs"""
            story_text = state.get('story_text', '')
            scenes = state.get('scenes', [])
            
            print("🎙️ Gerando áudio com ElevenLabs...")
            
            audio_files = []
            
            for i, scene in enumerate(scenes[:3]):  # Limit to 3 scenes
                try:
                    print(f"🎤 Gerando áudio para cena {scene['scene_id']}...")
                    
                    # Create output directory
                    os.makedirs('output', exist_ok=True)
                    audio_path = f"output/scene_{scene['scene_id']}_audio.mp3"
                    
                    # Generate audio using ElevenLabs
                    elevenlabs_api_key = os.getenv('ELEVENLABS_API_KEY')
                    
                    if elevenlabs_api_key:
                        import requests
                        import json
                        
                        # Prepare text for narration (scene description)
                        narration_text = f"Cena {scene['scene_id']}: {scene['description']}"
                        
                        # ElevenLabs API call
                        headers = {
                            'Accept': 'audio/mpeg',
                            'Content-Type': 'application/json',
                            'xi-api-key': elevenlabs_api_key
                        }
                        
                        data = {
                            'text': narration_text,
                            'model_id': 'eleven_multilingual_v2',  # Supports multiple languages
                            'voice_settings': {
                                'stability': 0.5,
                                'similarity_boost': 0.5
                            }
                        }
                        
                        # Use a default voice (you can customize this)
                        voice_url = 'https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM'
                        
                        response = requests.post(voice_url, headers=headers, json=data)
                        
                        if response.status_code == 200:
                            # Save real audio
                            with open(audio_path, 'wb') as f:
                                f.write(response.content)
                            
                            audio_files.append({
                                'scene_id': scene['scene_id'],
                                'audio_path': audio_path,
                                'text': narration_text,
                                'voice_id': '21m00Tcm4TlvDq8ikWAM',
                                'generation_method': 'elevenlabs'
                            })
                            
                            print(f"✅ Áudio ElevenLabs gerado: cena {scene['scene_id']}")
                            continue
                        else:
                            print(f"⚠️ ElevenLabs falhou: {response.status_code}")
                    
                    # Fallback mock generation
                    with open(audio_path, 'w') as f:
                        f.write(f"Mock audio: {narration_text}")
                    
                    audio_files.append({
                        'scene_id': scene['scene_id'],
                        'audio_path': audio_path,
                        'text': narration_text,
                        'generation_method': 'mock'
                    })
                    
                    print(f"✅ Áudio gerado (mock): cena {scene['scene_id']}")
                    
                except Exception as e:
                    print(f"⚠️ Erro ao gerar áudio para cena {scene['scene_id']}: {e}")
                    # Continue with next scene
            
            state.update({
                'audio_files': audio_files,
                'audio_count': len(audio_files),
                'current_step': 'audio_generated'
            })
            
            print(f"✅ {len(audio_files)} áudios gerados")
            return state
        
        def compile_video(state: Open3DAgentState) -> Open3DAgentState:
            """Compile final video using FFmpeg"""
            scene_images = state.get('scene_images', [])
            audio_files = state.get('audio_files', [])
            
            print("🎬 Compilando vídeo final com FFmpeg...")
            
            video_path = 'output/final_video.mp4'
            
            try:
                import subprocess
                import os
                
                # Create output directory
                os.makedirs('output', exist_ok=True)
                
                # Check if FFmpeg is available
                try:
                    subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
                    ffmpeg_available = True
                except (subprocess.CalledProcessError, FileNotFoundError):
                    ffmpeg_available = False
                    print("⚠️ FFmpeg não disponível, usando mock")
                
                if ffmpeg_available and scene_images:
                    print("🔧 Usando FFmpeg real para compilação...")
                    
                    # Create a temporary file list for FFmpeg
                    filelist_path = 'output/filelist.txt'
                    with open(filelist_path, 'w') as f:
                        for img in scene_images:
                            # Check if it's a real image file (not mock)
                            img_path = img['image_path']
                            if os.path.exists(img_path) and os.path.getsize(img_path) > 1000:  # Real image
                                duration = img.get('duration', 5)  # Default 5 seconds per scene
                                f.write(f"file '{img_path}'\n")
                                f.write(f"duration {duration}\n")
                    
                    # Compile video with images
                    if os.path.exists(filelist_path) and os.path.getsize(filelist_path) > 0:
                        temp_video = 'output/temp_video.mp4'
                        
                        # Create video from images
                        cmd = [
                            'ffmpeg', '-y',  # Overwrite output file
                            '-f', 'concat',  # Concat demuxer
                            '-safe', '0',    # Allow unsafe paths
                            '-i', filelist_path,  # Input file list
                            '-c:v', 'libx264',  # Video codec
                            '-pix_fmt', 'yuv420p',  # Pixel format for compatibility
                            '-r', '30',  # Frame rate
                            temp_video
                        ]
                        
                        result = subprocess.run(cmd, capture_output=True, text=True)
                        
                        if result.returncode == 0 and audio_files:
                            # Add audio to video
                            audio_path = None
                            for audio in audio_files:
                                if os.path.exists(audio['audio_path']) and os.path.getsize(audio['audio_path']) > 1000:
                                    audio_path = audio['audio_path']
                                    break
                            
                            if audio_path:
                                cmd = [
                                    'ffmpeg', '-y',
                                    '-i', temp_video,  # Video input
                                    '-i', audio_path,  # Audio input
                                    '-c:v', 'copy',    # Copy video stream
                                    '-c:a', 'aac',     # Audio codec
                                    '-shortest',       # Match shortest stream
                                    video_path
                                ]
                                
                                result = subprocess.run(cmd, capture_output=True, text=True)
                                
                                if result.returncode == 0:
                                    # Clean up temp file
                                    os.remove(temp_video)
                                    print(f"✅ Vídeo FFmpeg compilado com áudio: {video_path}")
                                else:
                                    print(f"⚠️ Erro ao adicionar áudio: {result.stderr}")
                                    # Use video without audio
                                    os.rename(temp_video, video_path)
                            else:
                                # No valid audio found, use video only
                                os.rename(temp_video, video_path)
                                print(f"✅ Vídeo FFmpeg compilado (sem áudio): {video_path}")
                        else:
                            print(f"⚠️ Erro na compilação FFmpeg: {result.stderr}")
                            # Fallback to mock
                            raise Exception("FFmpeg compilation failed")
                    else:
                        print("⚠️ Nenhuma imagem válida encontrada para FFmpeg")
                        raise Exception("No valid images for FFmpeg")
                
                else:
                    # Fallback to mock
                    raise Exception("FFmpeg not available or no images")
                
                state.update({
                    'video_path': video_path,
                    'video_size': os.path.getsize(video_path) if os.path.exists(video_path) else 0,
                    'generation_method': 'ffmpeg',
                    'current_step': 'video_compiled',
                    'status': 'completed'
                })
                
            except Exception as e:
                print(f"⚠️ FFmpeg falhou: {e}")
                print("💡 Usando mock de vídeo")
                
                # Fallback mock generation
                with open(video_path, 'w') as f:
                    f.write(f"Mock video compiled from {len(scene_images)} images and {len(audio_files)} audio files")
                
                state.update({
                    'video_path': video_path,
                    'video_size': os.path.getsize(video_path),
                    'generation_method': 'mock',
                    'current_step': 'video_compiled',
                    'status': 'completed'
                })
            
            print(f"✅ Vídeo finalizado: {video_path}")
            return state
        
        # Create workflow graph
        workflow = StateGraph(Open3DAgentState)
        
        # Add nodes
        workflow.add_node("extract_story", extract_story)
        workflow.add_node("generate_scenes", generate_scenes)
        workflow.add_node("generate_images", generate_images)
        workflow.add_node("generate_audio", generate_audio)
        workflow.add_node("compile_video", compile_video)
        
        # Set entry point
        workflow.set_entry_point("extract_story")
        
        # Add edges
        workflow.add_edge("extract_story", "generate_scenes")
        workflow.add_edge("generate_scenes", "generate_images")
        workflow.add_edge("generate_images", "generate_audio")
        workflow.add_edge("generate_audio", "compile_video")
        workflow.add_edge("compile_video", END)
        
        # Compile workflow
        compiled_workflow = workflow.compile()
        
        print("✅ Workflow LangGraph criado com sucesso!")
        return compiled_workflow
        
    except ImportError as e:
        print(f"❌ Erro ao importar dependências LangGraph: {e}")
        print("💡 Certifique-se de que langgraph está instalado")
        return None
    except Exception as e:
        print(f"❌ Erro ao criar workflow: {e}")
        return None



@dataclass
class WorkflowConfig:
    """Configuration for Open3D workflow"""
    max_iterations: int = 10
    enable_visualization: bool = True
    output_format: str = "mp4"
