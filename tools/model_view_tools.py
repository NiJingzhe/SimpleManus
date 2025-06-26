import numpy as np
import trimesh
import pyrender
from PIL import Image, ImageDraw, ImageFont
import os
from typing import Union, Optional
from pathlib import Path
from SimpleLLMFunc import tool
from SimpleLLMFunc.type import ImgPath

@tool(name="render_multi_view", description="生成3D模型的多视角合成渲染图，包含实体和线框渲染")
def render_multi_view_model(
    model_path: str,
    output_path: str = "multi_view_render.png",
    image_size: int = 512,
    background_color: str = "white",
    show_wireframe: bool = True
) -> ImgPath:
    """
    生成3D模型的多视角合成渲染图，在6个典型方向上渲染模型并合并为一张图
    
    Args:
        model_path: 3D模型文件路径 (支持 .obj, .stl, .ply, .glb, .gltf 等格式)
        output_path: 输出图像文件路径，默认为 "multi_view_render.png",建议提供和零件相关的语义化路径，例如 "DN100_PN16_法兰/multi_view_render.png"
        image_size: 每个视角的图像尺寸，默认512x512像素
        background_color: 背景颜色，可选 "white", "black", "transparent"，默认为白色
        show_wireframe: 是否显示线框，默认为True
        
    Returns:
        ImgPath: 渲染后的多视角合成图像文件路径
    """
    
    try:
        # 加载3D模型
        mesh = trimesh.load(model_path)
        
        # 如果是多个mesh，合并为一个
        if isinstance(mesh, trimesh.Scene):
            # 获取场景中的所有几何体并合并
            geometries = [geometry for geometry in mesh.geometry.values() if isinstance(geometry, trimesh.Trimesh)]
            if geometries:
                mesh = trimesh.util.concatenate(geometries)
            else:
                raise ValueError("场景中没有找到有效的三角网格")
        
        # 确保mesh是有效的
        if not isinstance(mesh, trimesh.Trimesh):
            raise ValueError("无法加载有效的3D模型")
        
        # 创建pyrender场景
        scene = pyrender.Scene(ambient_light=[0.3, 0.3, 0.3])
        
        # 为mesh添加材质
        solid_material = pyrender.MetallicRoughnessMaterial(
            metallicFactor=0.0,
            roughnessFactor=0.5,
            baseColorFactor=[0.8, 0.8, 0.8, 1.0]  # 浅灰色
        )
        
        # 线框材质
        wireframe_material = pyrender.MetallicRoughnessMaterial(
            metallicFactor=0.0,
            roughnessFactor=1.0,
            baseColorFactor=[0.2, 0.2, 0.2, 1.0]  # 深灰色线条
        )
        
        # 添加实体mesh到场景
        solid_mesh_node = pyrender.Mesh.from_trimesh(mesh, material=solid_material)
        solid_mesh_handle = scene.add(solid_mesh_node)
        
        # 添加线框mesh到场景（如果需要）
        wireframe_mesh_handle = None
        if show_wireframe:
            wireframe_mesh_node = pyrender.Mesh.from_trimesh(
                mesh, 
                material=wireframe_material,
                wireframe=True
            )
            wireframe_mesh_handle = scene.add(wireframe_mesh_node)
        
        # 设置背景颜色
        bg_colors = {
            "white": [1.0, 1.0, 1.0, 1.0],
            "black": [0.0, 0.0, 0.0, 1.0], 
            "transparent": [0.0, 0.0, 0.0, 0.0]
        }
        bg_color = bg_colors.get(background_color.lower(), [1.0, 1.0, 1.0, 1.0])
        
        # 获取模型的边界框来确定相机位置
        bounds = mesh.bounds
        center = mesh.centroid
        size = np.max(bounds[1] - bounds[0])
        
        # 相机距离 - 足够远以包含整个模型
        camera_distance = size * 1.5
        
        # 定义6个视角的方向和名称 - 包含正视图和斜视图
        views = [
            {
                "name": "Front View",
                "position": center + np.array([0, 0, camera_distance]),
                "target": center,
                "up": [0, 1, 0]
            },
            {
                "name": "Back View", 
                "position": center + np.array([0, 0, -camera_distance]),
                "target": center,
                "up": [0, 1, 0]
            },
            {
                "name": "Right Side",
                "position": center + np.array([camera_distance, 0, 0]),
                "target": center,
                "up": [0, 1, 0]
            },
            {
                "name": "Top-Left View",
                "position": center + np.array([-camera_distance*0.7, camera_distance*0.7, camera_distance*0.7]),
                "target": center,
                "up": [0, 1, 0]
            },
            {
                "name": "Top View",
                "position": center + np.array([0, camera_distance, 0]),
                "target": center,
                "up": [0, 0, -1]
            },
            {
                "name": "Bottom-Right View",
                "position": center + np.array([camera_distance*0.7, -camera_distance*0.7, camera_distance*0.7]),
                "target": center,
                "up": [0, 1, 0]
            }
        ]
        
        # 创建渲染器
        renderer = pyrender.OffscreenRenderer(image_size, image_size)
        
        # 渲染每个视角
        rendered_images = []
        
        for view in views:
            # 创建相机
            camera = pyrender.PerspectiveCamera(yfov=np.pi / 4.0, aspectRatio=1.0)
            
            # 使用更简单且可靠的方法设置相机
            # 计算从目标到相机位置的方向向量
            eye_pos = np.array(view["position"])
            target_pos = np.array(view["target"])
            up_vec = np.array(view["up"])
            
            # 构建正交坐标系
            forward = target_pos - eye_pos  # 从相机指向目标
            forward = forward / np.linalg.norm(forward)
            
            right = np.cross(forward, up_vec)
            if np.linalg.norm(right) < 1e-6:  # 处理平行情况
                # 如果forward和up平行，选择一个不同的up向量
                if abs(forward[0]) < 0.9:
                    up_vec = np.array([1, 0, 0])
                else:
                    up_vec = np.array([0, 1, 0])
                right = np.cross(forward, up_vec)
            right = right / np.linalg.norm(right)
            
            up = np.cross(right, forward)
            up = up / np.linalg.norm(up)
            
            # 构建相机变换矩阵 (world to camera)
            camera_pose = np.eye(4)
            camera_pose[:3, :3] = np.column_stack([right, up, -forward])
            camera_pose[:3, 3] = eye_pos
            
            print(f"渲染 {view['name']}: 相机位置 {eye_pos}, 目标 {target_pos}")
            
            # 添加相机到场景
            camera_node = scene.add(camera, pose=camera_pose)
            
            # 添加光源 
            light = pyrender.DirectionalLight(color=[1.0, 1.0, 1.0], intensity=1.5)
            light_node = scene.add(light, pose=camera_pose)
            
            # 渲染
            result = renderer.render(scene)
            if result is None:
                raise RuntimeError(f"渲染失败: {view['name']}")
            color, depth = result
            
            # 设置背景
            if background_color.lower() != "transparent":
                # 创建背景
                background = np.ones((image_size, image_size, 3), dtype=np.uint8) * int(bg_color[0] * 255)
                
                # 合成图像
                if color.shape[2] == 4:  # 有alpha通道
                    alpha = color[:, :, 3:4] / 255.0
                    color_rgb = color[:, :, :3]
                    final_color = color_rgb * alpha + background * (1 - alpha)
                    final_color = final_color.astype(np.uint8)
                else:
                    final_color = color[:, :, :3]
            else:
                final_color = color
            
            # 转换为PIL图像
            img = Image.fromarray(final_color)
            rendered_images.append((img, view["name"]))
            
            # 移除相机和光源
            scene.remove_node(camera_node)
            scene.remove_node(light_node)
        
        # 清理渲染器
        renderer.delete()
        
        # 创建合成图像
        # 如果显示线框，需要更多空间来显示标签
        text_height = 60 if show_wireframe else 40  # 为文字标注预留的高度
        single_view_height = image_size + text_height
        
        composite_width = image_size * 3
        composite_height = single_view_height * 2
        
        # 创建合成图像
        composite = Image.new('RGB', (composite_width, composite_height), 
                            (255, 255, 255) if background_color.lower() != "black" else (0, 0, 0))
        
        # 尝试加载字体
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 20)
            small_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 16)
        except:
            try:
                font = ImageFont.truetype("arial.ttf", 20)
                small_font = ImageFont.truetype("arial.ttf", 14)
            except:
                font = ImageFont.load_default()
                small_font = ImageFont.load_default()
        
        draw = ImageDraw.Draw(composite)
        text_color = (0, 0, 0) if background_color.lower() != "black" else (255, 255, 255)
        
        # 排列视图 (3x2网格)
        positions = [
            (0, 0),      # Front View
            (1, 0),      # Back View  
            (2, 0),      # Right Side
            (0, 1),      # Top-Left View
            (1, 1),      # Top View
            (2, 1)       # Bottom-Right View
        ]
        
        for i, ((img, name), (col, row)) in enumerate(zip(rendered_images, positions)):
            x = col * image_size
            y = row * single_view_height
            
            # 粘贴图像
            composite.paste(img, (x, y))
            
            # 添加文字标注
            text_y = y + image_size + 5
            
            # 计算文字位置以居中显示
            bbox = draw.textbbox((0, 0), name, font=font)
            text_width = bbox[2] - bbox[0]
            text_x = x + (image_size - text_width) // 2
            
            draw.text((text_x, text_y), name, fill=text_color, font=font)
            
            # 如果显示线框，添加额外说明
            if show_wireframe:
                wireframe_text = "(Solid + Wireframe)"
                bbox2 = draw.textbbox((0, 0), wireframe_text, font=small_font)
                text_width2 = bbox2[2] - bbox2[0]
                text_x2 = x + (image_size - text_width2) // 2
                draw.text((text_x2, text_y + 25), wireframe_text, fill=text_color, font=small_font)
        
        # 保存合成图像
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        composite.save(output_file)
        
        return ImgPath(str(output_file))
        
    except Exception as e:
        raise Exception(f"多视角渲染失败: {str(e)}")