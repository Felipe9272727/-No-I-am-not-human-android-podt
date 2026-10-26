#!/usr/bin/env python3
"""CPU reference captures of source sign Image layers, not Android Canvas execution.

The Firefighter human fixture uses PPtrs from generated/presentation_provider.hpp.
The layout, masks, frames and rectangles come from exported original scene data.
"""
import json
import hashlib
from pathlib import Path
from PIL import Image, ImageChops

ROOT=Path(__file__).resolve().parents[3]
ASSETS=ROOT/'reconstruction/android-current/app/src/main/assets'
OUT=ROOT/'reconstruction/android-current/qa/fidelity-v12'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    config=json.loads((ASSETS/'presentation/ui/sign_layout.json').read_text())
    ui=json.loads((ASSETS/'presentation/ui/ui_manifest.json').read_text())
    presentation=json.loads((ASSETS/'presentation/assets.json').read_text())
    animation=json.loads((ASSETS/presentation['animations_manifest']).read_text())
    items={item['path_id']:item for item in ui['components']}
    covers={row['image']['path_id']:row for row in animation['animated_image_components']}
    # Exact human assets from the statically recovered Firefighter record.
    fixture={0:{'white':1749,'iris':1605},1:{'content':1796},2:{'content':1777},
             3:{'content':2069},4:{'content':2365},5:{'content':1967}}

    def image_for(layer,kind):
        role=layer['role']
        if role!='static':
            key='sharedassets0.assets:'+str(fixture[kind][role])
            asset=presentation['images'][key]
        else:
            cover=covers.get(layer['image_id'])
            asset=cover['frames'][-1]['sprite']['android_asset'] if cover else items[layer['image_id']]['asset']
        return Image.open(ASSETS/asset).convert('RGBA')

    def positioned(image,rect,preserve):
        x,y,w,h=rect
        if preserve:
            scale=min(w/image.width,h/image.height);width=image.width*scale;height=image.height*scale
            x+=(w-width)/2;y+=(h-height)/2;w,h=width,height
        return image.transform((1920,1080),Image.Transform.AFFINE,
            (image.width/w,0,-x*image.width/w,0,image.height/h,-y*image.height/h),Image.Resampling.BILINEAR)

    report=[]
    for view in config['signs']:
        kind=view['enum_value'];canvas=Image.new('RGBA',(1920,1080),(24,24,24,255))
        for layer in view['layers_back_to_front']:
            image=image_for(layer,kind);item=items[layer['image_id']]
            tint=item['image']['color_rgba']
            image=Image.merge('RGBA',tuple(channel.point([round(v*tint[i]) for v in range(256)]) for i,channel in enumerate(image.split())))
            pixel=positioned(image,layer['screen_rect_1920x1080'],layer['preserve_aspect'])
            if layer['mask_image_id']>=0:
                mask_item=items[layer['mask_image_id']]
                mask_image=Image.open(ASSETS/mask_item['asset']).convert('RGBA')
                mask=positioned(mask_image,mask_item['rect_transform']['screen_rect_1920x1080'],mask_item['image']['preserve_aspect'])
                pixel.putalpha(ImageChops.multiply(pixel.getchannel('A'),mask.getchannel('A')))
            canvas=Image.alpha_composite(canvas,pixel)
        path=OUT/('sign-'+view['name']+'-source-reference.png');canvas.convert('RGB').save(path)
        difference=ImageChops.difference(canvas.convert('RGB'),Image.new('RGB',canvas.size,(24,24,24)))
        bounds=difference.getbbox()
        if bounds is None:raise AssertionError('empty source sign capture: '+view['name'])
        report.append({'sign':view['name'],'image_ids':[x['image_id'] for x in view['layers_back_to_front']],
                       'capture':str(path.relative_to(ROOT)),'visible_bounds':list(bounds)})
    summary={'method':'PIL CPU source layout reference, settled content/end frame; no Android Canvas execution',
             'fixture':'Firefighter human original sprites',
             'staged_sign_layout_sha256':hashlib.sha256((ASSETS/'presentation/ui/sign_layout.json').read_bytes()).hexdigest(),
             'views':report,'android_canvas_tested':False,'eye_random_motion_implemented':False}
    (ROOT/'reconstruction/android-current/sign_layout_v12_validation.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('Source inspection references rendered:',len(report))


if __name__=='__main__':main()
