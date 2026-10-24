"""Little Wizard: editable, rigged character assets. Run in Blender 5.2.
Coordinates: metres, Z up, front -Y. All geometry is authored locally.

V5: every wizard gets a rebuilt head from wizard_hair_v5.py (layered, tapered
locks instead of V4's round tubes; sculpted ears; rounder face with a pointed
chin; lash lines, creases and brows) plus a slim neck.  Bodies and clothing are
V4's.
  blender -b -P build_wizard_models_v5.py -- wind          full build + FBX
  blender -b -P build_wizard_models_v5.py -- wind head     fast head-only renders
"""
import bpy, math, random, json, sys
from pathlib import Path
from mathutils import Vector, Matrix
from math import sin, cos, pi
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
OUT=ROOT/'output'/'wizard-models'/'v5'
OUT.mkdir(parents=True,exist_ok=True)
ARGS=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
KIND=ARGS[0] if ARGS else 'fire'
HEAD_ONLY='head' in ARGS
random.seed(37)
bpy.ops.wm.read_factory_settings(use_empty=True)
scene=bpy.context.scene
scene.unit_settings.system='METRIC'
scene.unit_settings.scale_length=1.0
parts=[]; mats={}; bones={}
def mat(name,color,rough=.6,metal=0):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Roughness'].default_value=rough;p.inputs['Metallic'].default_value=metal
    mats[name]=m;return m
# round 21: the off-whites were near pure white (blown out in the renders and in the game); the 3d-v2
# sheets' coats, robes, hats and hoodies are a warm cream: Ivory .94/.88/.75 -> .80/.74/.63, Cream a little too
mat('Skin',(0.68,.36,.22),.57);mat('Ear',(0.53,.19,.13));mat('Cream',(.76,.68,.53));mat('Ivory',(.80,.74,.63));mat('Gold',(.68,.39,.105),.34,.55)
mat('Dark',(.055,.043,.039));mat('Sole',(.58,.49,.37));mat('White',(.96,.94,.88),.25);mat('Pupil',(.011,.009,.018),.22)
mat('Mouth',(.15,.026,.025));mat('Lip',(.47,.17,.125));mat('Red',(.47,.049,.027));mat('RedLight',(.7,.11,.038));mat('Orange',(.63,.23,.041),.4);mat('OrangeLight',(.88,.4,.095),.4)
mat('Purple',(.20,.078,.32));mat('PurpleLight',(.36,.18,.50));mat('Blue',(.16,.30,.51));mat('Lavender',(.40,.38,.58));mat('IceHair',(.20,.075,.30),.4);mat('IceHairLight',(.36,.15,.47),.42)
mat('Green',(.12,.18,.075));mat('GreenHair',(.019,.075,.047),.48);mat('GreenHairLight',(.055,.15,.085),.46);mat('Khaki',(.36,.245,.083));mat('Silver',(.75,.69,.72),.38);mat('SilverLight',(.91,.86,.87),.35)
mat('Stubble',(.085,.10,.066),.95)
mat('Brown',(.135,.062,.034),.55)
mat('IcePants',(.20,.215,.42),.75)
import wizard_outfit_v5 as OUTFIT   # round 8: shoes, trousers, sleeves, garments
COL={'fire':('Red','Gold','Orange','OrangeLight','RedLight'),'ice':('Lavender','Blue','IceHair','IceHairLight','Blue'),'wind':('Green','Khaki','GreenHair','GreenHairLight','Green'),'lightning':('Purple','Gold','Silver','SilverLight','PurpleLight')}
accent,trim,hair,hairhi,iris=COL[KIND]
for nm,col in {'Orange':(.53,.155,.018),'OrangeLight':(.75,.28,.038),'Red':(.38,.028,.017),'IceHair':(.145,.032,.245),'IceHairLight':(.26,.09,.37),'Purple':(.16,.035,.26),'Lavender':(.29,.27,.48)}.items():
    mats[nm].diffuse_color=(*col,1);mats[nm].node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(*col,1)
def weights(obj,w):
    groups={}
    for v in obj.data.vertices:
        d=w(v.co) if callable(w) else {w:1}
        for name,value in d.items():
            if value>1e-6:
                if name not in groups:groups[name]=obj.vertex_groups.new(name=name)
                groups[name].add([v.index],value,'REPLACE')
def finish(obj,name,material,w,sub=0):
    obj.name=name;obj.data.materials.append(mats[material]);parts.append(obj)
    bpy.context.view_layer.objects.active=obj
    bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
    if sub:
        mod=obj.modifiers.new('Surface refinement','SUBSURF');mod.levels=sub
        bpy.ops.object.modifier_apply(modifier=mod.name)
    for p in obj.data.polygons:p.use_smooth=True
    weights(obj,w);return obj
def mesh(name,vs,fs,material,w,sub=0):
    me=bpy.data.meshes.new(name);me.from_pydata(vs,[],fs);me.update()
    ob=bpy.data.objects.new(name,me);scene.collection.objects.link(ob)
    bpy.ops.object.select_all(action='DESELECT');ob.select_set(True)
    return finish(ob,name,material,w,sub)
def ell(name,loc,scale,material,w,segments=24,rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments,ring_count=rings,location=loc)
    ob=bpy.context.object;ob.scale=scale;return finish(ob,name,material,w)
def box(name,loc,scale,material,w,bevel=.01):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);ob=bpy.context.object;ob.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if bevel:
        m=ob.modifiers.new('Soft edges','BEVEL');m.width=bevel;m.segments=3
        bpy.ops.object.modifier_apply(modifier=m.name)
    return finish(ob,name,material,w)
def tube(name,points,radii,material,w,sides=12):
    points=[Vector(p) for p in points];vs=[];fs=[]
    for i,p in enumerate(points):
        t=points[min(i+1,len(points)-1)]-points[max(i-1,0)];t.normalize()
        ref=Vector((0,1,0)) if abs(t.y)<.9 else Vector((1,0,0))
        a=t.cross(ref).normalized();b=t.cross(a).normalized()
        rr=radii[i] if isinstance(radii,list) else radii
        rx,ry=rr if isinstance(rr,tuple) else (rr,rr)
        for j in range(sides):vs.append(p+a*(rx*cos(2*pi*j/sides))+b*(ry*sin(2*pi*j/sides)))
    for i in range(len(points)-1):
        for j in range(sides):
            a=i*sides+j;b=i*sides+(j+1)%sides;fs.append((a,b,b+sides,a+sides))
    if not any(v in name for v in ['sleeve','lining','piping','collar']):
        fs.extend([tuple(range(sides-1,-1,-1)),tuple((len(points)-1)*sides+j for j in range(sides))])
    return mesh(name,vs,fs,material,w)
def bez(points,n=18):
    a,b,c,d=map(Vector,points)
    return [a*(1-t)**3+b*3*t*(1-t)**2+c*3*t*t*(1-t)+d*t**3 for t in [i/(n-1) for i in range(n)]]
def strand(name,points,width,depth,material,w='head',ridge=False):
    ps=bez(points);rr=[(max(.0008,width*(sin(pi*(i/(len(ps)-1)))*.75+.18)*(1-i/(len(ps)-1))**.25),max(.0007,depth*sin(pi*i/(len(ps)-1))**.5)) for i in range(len(ps))]
    ob=tube(name,ps,rr,material,w,10)
    if ridge:
        qs=[p+Vector((0,-depth*.88,0)) for p in ps[2:-2]]
        tube(name+' sheen',qs,.0013,hairhi,w,5)
    return ob
def loft(name,rings,material,w,n=40,fold=0,cap=True):
    # rings: z, radius x, radius y, center y. Soft tailored folds.
    vs=[];fs=[]
    for i,(z,rx,ry,cy) in enumerate(rings):
        for j in range(n):
            a=2*pi*j/n;f=1+fold*sin(a*10+i*.7)
            vs.append((rx*cos(a)*f,cy+ry*sin(a)*f,z))
    for i in range(len(rings)-1):
        for j in range(n):
            a=i*n+j;b=i*n+(j+1)%n;fs.append((a,b,b+n,a+n))
    if cap:fs.extend([tuple(range(n-1,-1,-1)),tuple((len(rings)-1)*n+j for j in range(n))])
    return mesh(name,vs,fs,material,w,1)
def chainweight(p,chain):
    # Linear interpolation over explicit axial control positions.
    z=p.z
    if z<=chain[0][0]:return {chain[0][1]:1}
    for (a,b),(c,d) in zip(chain,chain[1:]):
        if z<=c:
            t=(z-a)/(c-a);return {b:1-t,d:t} if b!=d else {b:1}
    return {chain[-1][1]:1}
def torso(p):return chainweight(p,[(.73,'pelvis'),(.88,'spine_01'),(1.03,'spine_02'),(1.15,'spine_03'),(1.23,'neck_01')])
def armweight(s):
    def f(p):
        # along shoulder-wrist diagonal, blend across elbow
        t=(abs(p.x)-.19)/.29
        a=max(0,min(1,(t-.35)/.3))
        if t>.87:
            b=max(0,min(1,(t-.87)/.2));return {'lowerarm_'+s:1-b,'hand_'+s:b}
        return {'upperarm_'+s:1-a,'lowerarm_'+s:a}
    return f
def legweight(s):return lambda p:chainweight(p,[(.12,'foot_'+s),(.22,'calf_'+s),(.36,'calf_'+s),(.48,'thigh_'+s),(.71,'thigh_'+s),(.78,'pelvis')])
def coatweight(p):
    if p.z>.8:return torso(p)
    left=max(0,min(1,(p.x+.09)/.18));front=max(0,min(1,(-p.y+.08)/.16));result={}
    for side,sw in [('l',left),('r',1-left)]:
        for face,fw in [('front',front),('back',1-front)]:
            for name,value in chainweight(p,[(.39,f'cloth_{face}_02_{side}'),(.60,f'cloth_{face}_01_{side}'),(.8,'pelvis')]).items():
                result[name]=result.get(name,0)+value*sw*fw
    return result
def bone(name,h,t,parent=None):bones[name]=(Vector(h),Vector(t),parent)
bone('root',(0,0,0),(0,0,.15))
bone('pelvis',(0,0,.72),(0,0,.82),'root')
bone('spine_01',(0,0,.82),(0,0,.94),'pelvis');bone('spine_02',(0,0,.94),(0,0,1.06),'spine_01');bone('spine_03',(0,0,1.06),(0,0,1.17),'spine_02')
bone('neck_01',(0,0,1.17),(0,0,1.25),'spine_03');bone('head',(0,0,1.25),(0,0,1.60),'neck_01')
for s,sg in [('l',1),('r',-1)]:
    bone('clavicle_'+s,(sg*.025,0,1.145),(sg*.19,0,1.14),'spine_03')
    bone('upperarm_'+s,(sg*.19,0,1.14),(sg*.345,0,.975),'clavicle_'+s)
    bone('lowerarm_'+s,(sg*.345,0,.975),(sg*.47,-.008,.815),'upperarm_'+s)
    bone('hand_'+s,(sg*.47,-.008,.815),(sg*.52,-.014,.744),'lowerarm_'+s)
    for k in range(4):
        x=sg*(.507+(k-1.5)*.016);z=.742+(k-1.5)*.011
        lengths=[.043,.054,.050,.039];end=Vector((x+sg*.025,-.014,z-lengths[k]))
        start=Vector((x,-.014,z));mid=start.lerp(end,.52)
        nm=['index','middle','ring','pinky'][k]
        bone(nm+'_01_'+s,start,mid,'hand_'+s);bone(nm+'_02_'+s,mid,end,nm+'_01_'+s)
    bone('thumb_01_'+s,(sg*.476,-.026,.775),(sg*.462,-.035,.743),'hand_'+s)
    bone('thumb_02_'+s,(sg*.462,-.035,.743),(sg*.474,-.04,.719),'thumb_01_'+s)
    bone('thigh_'+s,(sg*.10,0,.73),(sg*.127,-.012,.43),'pelvis')
    bone('calf_'+s,(sg*.127,-.012,.43),(sg*.14,0,.145),'thigh_'+s)
    bone('foot_'+s,(sg*.14,0,.145),(sg*.14,-.10,.067),'calf_'+s)
    bone('ball_'+s,(sg*.14,-.10,.067),(sg*.14,-.18,.06),'foot_'+s)
    for f,y in [('front',-.12),('back',.12)]:
        bone(f'cloth_{f}_01_{s}',(sg*.13,y,.79),(sg*.19,y*1.6,.58),'pelvis')
        bone(f'cloth_{f}_02_{s}',(sg*.19,y*1.6,.58),(sg*.23,y*1.9,.35),f'cloth_{f}_01_{s}')
    bone('hair_01_'+s,(sg*.19,.045,1.49),(sg*.235,.13,1.15),'head')
    bone('hair_02_'+s,(sg*.235,.13,1.15),(sg*.29,.16,.76),'hair_01_'+s)
bone('hair_back_01',(0,.18,1.48),(0,.20,1.10),'head');bone('hair_back_02',(0,.20,1.10),(0,.23,.72),'hair_back_01')
bone('scarf_01',(0,-.13,1.1),(0,-.15,.88),'spine_03');bone('scarf_02',(0,-.15,.88),(0,-.18,.58),'scarf_01')

# V2 facial anatomy and portable deform-bone controls.
girl=KIND in ['ice','lightning']
def recolor(n,c,rough=None):
    mats[n].diffuse_color=(*c,1);p=mats[n].node_tree.nodes['Principled BSDF'];p.inputs['Base Color'].default_value=(*c,1)
    if rough is not None:p.inputs['Roughness'].default_value=rough
recolor('Skin',(.82,.52,.39) if girl else ((.77,.43,.29) if KIND=='wind' else (.72,.365,.20)),.48)
if KIND=='wind':recolor('Green',(.062,.070,.027),.7)
recolor('Ear',(.63,.255,.21) if girl else (.49,.19,.095))
recolor('Pupil',(.005,.003,.012),.38)
mats['Pupil'].node_tree.nodes['Principled BSDF'].inputs['Specular IOR Level'].default_value=.12
recolor('Red',(.64,.018,.012));recolor('RedLight',(.95,.115,.023))
recolor('Orange',(.69,.135,.014),.45);recolor('OrangeLight',(.98,.34,.028),.42)
mat('EyeRim',(.058,.026,.055),.38)
mat('Blush',(.80,.32,.30),.65)
mat('IrisOuter',{'fire':(.20,.012,.003),'ice':(.042,.034,.105),'wind':(.021,.060,.030),'lightning':(.07,.018,.17)}[KIND],.28)
mat('IrisMain',{'fire':(.88,.13,.015),'ice':(.22,.245,.47),'wind':(.17,.29,.095),'lightning':(.42,.14,.70)}[KIND],.24)
mat('IrisInner',{'fire':(1.0,.42,.026),'ice':(.43,.42,.66),'wind':(.39,.48,.15),'lightning':(.7,.35,.91)}[KIND],.22)
mat('IrisRay',{'fire':(.98,.28,.018),'ice':(.31,.33,.55),'wind':(.12,.45,.15),'lightning':(.56,.23,.78)}[KIND],.27)
# (round 7: blink and the open mouth are morph targets, so no jaw / eyelid bones)
bone('face_lip_upper',(0,-.148,1.307),(0,-.148,1.327),'head')
bone('face_lip_lower',(0,-.149,1.274),(0,-.149,1.294),'head')
bone('face_nose',(0,-.166,1.353),(0,-.166,1.378),'head')
for side,sg in [('l',1),('r',-1)]:
    for nm,xyz in [('eye',(sg*.09,-.175,1.414)),('gaze',(sg*.09,-.195,1.414)),('brow',(sg*.09,-.163,1.482)),('smile',(sg*.05,-.14,1.297)),('cheek',(sg*.14,-.13,1.335))]:
        parent='face_eye_'+side if nm=='gaze' else 'head'
        bone('face_'+nm+'_'+side,xyz,(xyz[0],xyz[1],xyz[2]+.025),parent)
# 75 total bones. Face weights fade into the surrounding head; mouth pieces use same controls.
def faceweight(p):
    front=max(0,min(1,(-p.y-.035)/.08));jaw=max(0,min(.90,(1.300-p.z)/.040))*front
    d={'face_jaw':jaw}
    lipx=math.exp(-(p.x/.060)**4)*front
    lower=math.exp(-((p.z-1.276)/.014)**2)*lipx*.55
    upper=math.exp(-((p.z-1.303)/.010)**2)*lipx*.65
    d['face_jaw']*=1-lower
    d['face_lip_lower']=lower;d['face_lip_upper']=upper
    d['face_nose']=.8*math.exp(-(p.x/.019)**2-((p.z-1.355)/.027)**2)*front
    for side,sg in [('l',1),('r',-1)]:
        for nm,cx,cz,sx,sz,strength in [('smile',.054,1.300,.041,.036,.40),('cheek',.139,1.345,.039,.041,.28),('brow',.092,1.485,.064,.027,.50)]:
            value=math.exp(-((p.x-sg*cx)/sx)**2-((p.z-cz)/sz)**2)*front*strength
            d['face_'+nm+'_'+side]=value
    total=sum(d.values())
    if total>.95:d={k:v*.95/total for k,v in d.items()};total=.95
    d['head']=1-total
    d=dict(sorted(d.items(),key=lambda x:x[1],reverse=True)[:4]);sm=sum(d.values())
    return {k:v/sm for k,v in d.items()}
if KIND=='wind':
    profile=[(1.20,.035,.064,-.021),(1.226,.082,.101,-.016),(1.256,.139,.136,-.008),(1.29,.174,.153,0),(1.35,.194,.165,.003),(1.43,.217,.177,.011),(1.52,.20,.17,.018),(1.60,.135,.12,.018),(1.635,.018,.02,.015)]
elif girl:
    profile=[(1.205,.032,.048,-.009),(1.235,.087,.09,-.009),(1.27,.146,.129,-.003),(1.325,.184,.152,.005),(1.385,.204,.170,.008),(1.47,.207,.174,.012),(1.55,.185,.16,.02),(1.61,.125,.115,.018),(1.635,.018,.02,.015)]
else:
    profile=[(1.20,.042,.054,-.009),(1.23,.10,.096,-.012),(1.268,.151,.129,-.006),(1.315,.193,.151,0),(1.38,.213,.177,.002),(1.47,.216,.176,.012),(1.55,.19,.16,.02),(1.61,.128,.115,.018),(1.635,.018,.02,.015)]
dense=[]
for idx,(a,b) in enumerate(zip(profile,profile[1:])):
    before=profile[max(0,idx-1)];after=profile[min(len(profile)-1,idx+2)]
    count=max(1,math.ceil((b[0]-a[0])/.009))
    for i in range(count):
        t=i/count;dz=b[0]-a[0];values=[a[0]+t*dz]
        for j in range(1,4):
            m0=(b[j]-before[j])/(b[0]-before[0]);m1=(after[j]-a[j])/(after[0]-a[0])
            values.append((2*t**3-3*t*t+1)*a[j]+(t**3-2*t*t+t)*dz*m0+(-2*t**3+3*t*t)*b[j]+(t**3-t*t)*dz*m1)
        dense.append(tuple(values))
dense.append(profile[-1])
faceob=loft('Face refined cheek and jaw',dense,'Skin',faceweight,128)
# Sculpt the anterior face into a broad cheek plane with an integrated nose.
# Keep the cranial back round. The nose is part of this same continuous mesh.
for v in faceob.data.vertices:
    x,y,z=v.co
    for a,b in zip(dense,dense[1:]):
        if z<=b[0]:
            t=max(0,min(1,(z-a[0])/(b[0]-a[0])));row=tuple(a[k]*(1-t)+b[k]*t for k in range(4));break
    else:row=dense[-1]
    _,rx,ry,cy=row
    if y<cy:
        q=min(1,abs(x)/max(.001,rx))
        anterior=(max(0,1-q**2.65))**.5
        v.co.y=cy-ry*anterior
        front=max(0,1-q**6)
        bridge=.010*math.exp(-(x/.012)**2-((z-1.370)/.025)**2)
        tip=.017*math.exp(-(x/.0135)**2-((z-1.348)/.010)**2)
        cheeks=.003*math.exp(-((abs(x)-.118)/.045)**2-((z-1.345)/.028)**2)
        sockets=.0028*math.exp(-((abs(x)-.097)/.053)**4-((z-1.413)/.032)**4)
        v.co.y+=front*(sockets-bridge-tip-cheeks)
faceob.data.update()
faceob.vertex_groups.clear();weights(faceob,faceweight)
if girl:
    # Blush belongs to the skin surface itself, without floating geometry.
    for j in range(1,13):
        nm='Skin blush '+str(j);skin=Vector(mats['Skin'].diffuse_color[:3])
        mat(nm,skin.lerp(Vector((.87,.24,.24)),j/12*.20),.48)
        faceob.data.materials.append(mats[nm])
    for p in faceob.data.polygons:
        pos=p.center
        amount=max(math.exp(-((pos.x-sg*.14)/.037)**2-((pos.z-1.340)/.020)**2) for sg in [-1,1]) if pos.y<-.08 else 0
        p.material_index=round(12*amount)
from mathutils.bvhtree import BVHTree
facebvh=BVHTree.FromPolygons([v.co for v in faceob.data.vertices],[list(p.vertices) for p in faceob.data.polygons])
loft('Neck',[(1.10,.058,.050,.004),(1.15,.052,.046,.006),(1.20,.044,.042,.014),(1.26,.045,.044,.024),(1.335,.048,.047,.032)],'Skin',lambda p:chainweight(p,[(1.13,'spine_03'),(1.19,'neck_01'),(1.27,'head')]),32)
def surface(x,z):
    hit,normal,index,distance=facebvh.ray_cast(Vector((x,-1,z)),Vector((0,1,0)))
    if hit is not None:return hit.y
    for a,b in zip(profile,profile[1:]):
        if z<=b[0]:
            t=max(0,min(1,(z-a[0])/(b[0]-a[0])));rx=a[1]*(1-t)+b[1]*t;ry=a[2]*(1-t)+b[2]*t;cy=a[3]*(1-t)+b[3]*t
            return cy-ry*math.sqrt(max(.025,1-(x/rx)**2))
    return -.10
for sg in [-1,1]:
    side='l' if sg==1 else 'r';eb='face_eye_'+side;gb='face_gaze_'+side
    ell('Ear',(sg*.212,.003,1.365),(.039,.027,.055),'Skin','head',32,20)
    ell('Ear concha',(sg*.231,-.020,1.365),(.017,.004,.029),'Ear','head',32,20)
    ep=[(sg*(.225+.018*cos(a)),-.025,1.369+.039*sin(a)) for a in [2*pi*j/36 for j in range(37)]]
    tube('Ear helix',ep,.005,'Skin','head',10)
    tube('Ear antihelix',[(sg*.224,-.029,1.345),(sg*.230,-.030,1.363),(sg*.219,-.025,1.389)],[.004,.004,.002],'Skin','head',10)
    ex=sg*.097;ez=1.413;ew=.054 if girl else .058
    eh={'fire':.041,'ice':.034,'wind':.034,'lightning':.041}[KIND]
    topfactor={'fire':.90,'ice':.55,'wind':.60,'lightning':.92}[KIND];bottomfactor=.90
    tilt=.12 if KIND=='fire' else (.08 if KIND=='wind' else .07)
    def eyey(x,z):return surface(x,z)-.001
    # Curved eye disk with more iris coverage, round pupil and fine radial iris structure.
    vs=[(ex,eyey(ex,ez)-.0018,ez)];fs=[];N=64;R=9
    for rj in range(1,R+1):
        r=rj/R
        for j in range(N):
            a=2*pi*j/N;x=ex+ew*r*cos(a);z=ez+eh*r*(1 if sin(a)>=0 else -1)*abs(sin(a))**1.35*(topfactor if sin(a)>=0 else bottomfactor)+sg*(x-ex)*tilt
            vs.append((x,eyey(x,z)-.0018*(1-r*r),z))
    for j in range(N):fs.append((0,1+j,1+(j+1)%N))
    for rj in range(R-1):
        for j in range(N):a=1+rj*N+j;b=1+rj*N+(j+1)%N;fs.append((a,b,b+N,a+N))
    mesh('Eye white '+side,vs,fs,'White',eb)
    iw={'fire':.034,'ice':.030,'wind':.031,'lightning':.033}[KIND]
    ih=iw*.94
    def eyeclip(x,z):
        q=min(1,abs((x-ex)/ew));h=(1-q*q)**.675
        center=ez+sg*(x-ex)*tilt
        return max(center-eh*bottomfactor*h+.0007,min(center+eh*topfactor*h-.0007,z))
    def disk(name,r0,r1,material,depth):
        vv=[];ff=[]
        for radius in [r0+(r1-r0)*i/5 for i in range(6)]:
            for j in range(N):
                a=2*pi*j/N;x=ex+iw*radius*cos(a);z=eyeclip(x,ez-.001+ih*radius*sin(a))
                vv.append((x,eyey(x,z)-depth,z))
        for row in range(5):
            for j in range(N):
                a=row*N+j;b=row*N+(j+1)%N;ff.append((a,b,b+N,a+N))
        return mesh(name+' '+side,vv,ff,material,gb)
    disk('Iris limbal rim',.88,1.0,'IrisOuter',.0030)
    disk('Iris color',.59,.89,'IrisMain',.0033)
    disk('Iris inner light',.0,.60,'IrisInner',.0036)
    for j in range(24):
        a=2*pi*j/24;vv=[]
        for r,da in [(.61,-.007),(.86,0),(.61,.025)]:
            x=ex+iw*r*cos(a+da);z=eyeclip(x,ez-.001+ih*r*sin(a+da));vv.append((x,eyey(x,z)-.0038,z))
        mesh('Iris radial fiber '+side,vv,[(0,1,2)],'IrisRay',gb)
    disk('Large pupil',0,.62 if girl else .62,'Pupil',.0041)
    for dx,dz,rx,rz in [(-.006,.007,.004,.005),(.008,-.008,.0017,.0022)]:
        x=ex+dx;z=eyeclip(x,ez+dz)
        ell('Eye catchlight '+side,(x,eyey(x,z)-.0052,z),(rx,.0015,rz),'White',gb,20,12)
    for upper in [True,False]:
        pts=[]
        for i in range(25):
            t=i/24;x=ex-ew+2*ew*t;z=ez+(1 if upper else -1)*eh*max(0,1-((x-ex)/ew)**2)**.675*(topfactor if upper else bottomfactor)+sg*(x-ex)*tilt
            pts.append((x,eyey(x,z)-.002,z))
        tube(('Upper' if upper else 'Lower')+' eyelid '+side,pts,.0025 if upper else .0009,'EyeRim' if upper else 'Ear','face_lid_'+side if upper else eb,10)
    if girl:
        for j in range(2):
            x=ex+sg*(ew-.006-j*.010);z=ez+.011+j*.004
            tube('Soft eyelash '+side,[(x,eyey(x,z)-.004,z),(x+sg*.010,eyey(x,z)-.003,z+.010)], [.0025,.0004],'EyeRim','face_lid_'+side,6)
    inner={'fire':1.467,'wind':1.474,'ice':1.461,'lightning':1.470}[KIND]
    outer={'fire':1.489,'wind':1.478,'ice':1.465,'lightning':1.477}[KIND]
    points=[]
    for i in range(17):
        t=i/16;x=ex+sg*(-.051+.103*t);z=inner*(1-t)+outer*t+.004*sin(pi*t)
        points.append((x,surface(x,z)-.007,z))
    tube('Expressive eyebrow '+side,points,[.001+(.0018 if girl else .0035)*sin(pi*i/16)**.4 for i in range(17)],'EyeRim' if girl else hair,'face_brow_'+side,10)
smilek={'fire':-.010,'lightning':-.008,'ice':.003,'wind':.003}[KIND]
def mouthweight(p):
    # Follow the actual upper and lower edges, including the almost closed pout.
    t=max(0,min(1,(p.x+wide)/(2*wide)));c=sin(pi*t)
    top=1.311+smilek*c
    if KIND=='wind':top+=p.x*.015
    lower=max(0,min(1,(top-p.z)/max(.0003,openheight*c)))
    corner=min(.35,abs(p.x)/wide*.35);side='l' if p.x>=0 else 'r'
    return {'face_lip_upper':(1-lower)*(1-corner),'face_jaw':lower*.70*(1-corner),'face_lip_lower':lower*.30*(1-corner),'face_smile_'+side:corner}

def teethweight(p):
    side='l' if p.x>=0 else 'r';corner=min(.45,abs(p.x)/.058*.45)
    return {'face_smile_'+side:corner,'face_lip_upper':1-corner}
wide={'fire':.084,'ice':.021,'wind':.023,'lightning':.066}[KIND]
openheight={'fire':.044,'ice':.0015,'wind':.0015,'lightning':.064}[KIND]
mv=[];mf=[]
for i in range(41):
    t=i/40;x=-wide+2*wide*t;c=sin(pi*t);top=1.311+smilek*c
    if KIND=='wind':top+=x*.015
    low=top-openheight*c
    mv.extend([(x,surface(x,top)-.004,top),(x,surface(x,low)-.005,low)])
    if i:mf.append((2*i-2,2*i-1,2*i+1,2*i))
mesh('Sculpted smile opening',mv,mf,'Mouth',mouthweight)
if KIND in ['fire','lightning']:
    tv=[];tf=[]
    for i in range(33):
        t=i/32;x=wide*.88*(2*t-1);z=1.311+smilek*sin(pi*((x+wide)/(2*wide)))-.001
        tv.extend([(x,surface(x,z)-.007,z),(x,surface(x,z)-.007,z-(.020 if KIND=='fire' else .007)*sin(pi*t)**.5)])
        if i:tf.append((2*i-2,2*i-1,2*i+1,2*i))
    mesh('Single rounded tooth row',tv,tf,'White',teethweight)
pts=[]
for i in range(25):
    t=i/24;x=-wide+2*wide*t;z=1.311+(smilek-openheight)*sin(pi*t)+(x*.015 if KIND=='wind' else 0)
    pts.append((x,surface(x,z)-.004,z))
tube('Soft lower lip contour',pts,.0007,'Lip',mouthweight,8)

if KIND=='lightning':
    mat('Tongue',(.55,.12,.115),.65)
    vv=[];ff=[]
    for i in range(25):
        t=i/24;x=.044*(2*t-1);z=1.262+.010*sin(pi*t)
        vv.extend([(x,surface(x,z)-.0055,z),(x,surface(x,z)-.0055,z-.012*sin(pi*t)**.7)])
        if i:ff.append((2*i-2,2*i-1,2*i+1,2*i))
    mesh('Small tongue',vv,ff,'Tongue',mouthweight)
    # two little fangs at the corners of the upper teeth
    for sg in [-1,1]:
        x0=sg*wide*.52;z0=1.311+smilek*sin(pi*(x0+wide)/(2*wide))-.006
        fv=[(x0-.0065,surface(x0-.0065,z0)-.0075,z0),(x0+.0065,surface(x0+.0065,z0)-.0075,z0),(x0+sg*.002,surface(x0,z0-.013)-.0075,z0-.013)]
        mesh('Fang',fv,[(0,1,2) if sg<0 else (0,2,1)],'White',teethweight)

def headmap(p):
    jawlift=.075*max(0,min(1,(p.y+.06)/.20))*max(0,min(1,(1.42-p.z)/.20))
    z=p.z+jawlift
    if z<1.413:z=1.413+(z-1.413)*.80
    return Vector((p.x*.88,p.y*.94,1.245+(z-1.20)*.90))
for ob in parts:
    if ob.name=='Neck':continue
    for v in ob.data.vertices:v.co=headmap(v.co)
for name,(h,t,parent) in list(bones.items()):
    if name.startswith('face_'):bones[name]=(headmap(Vector(h)),headmap(Vector(t)),parent)
facebvh=BVHTree.FromPolygons([v.co for v in faceob.data.vertices],[list(p.vertices) for p in faceob.data.polygons])

# V5: cranium, ears, face shape, eyes, brows, scalp and hair for every wizard are
# built by wizard_hair_v5.py from its per-character STYLES table.
import wizard_hair_v5
wizard_hair_v5.build_head(globals())

# Body retained from V2.
# Round 9: sloped shoulders (no shrug).  Wind's shirt has broad, nearly flat
# shoulders (3d-v2); fire's shirt stays inside the coat; the others' tops are
# wide over the shoulder joint so the hanging sleeves start inside them.
TUNIC={'wind':[(.72,.135,.088,0),(.78,.153,.10,0),(.85,.132,.096,0),(.94,.142,.10,0),(1.0,.160,.104,0),(1.05,.171,.108,0),(1.10,.176,.104,0),(1.135,.174,.098,0),(1.155,.162,.088,0),(1.168,.121,.074,0),(1.177,.084,.058,0)],
       'fire':[(.72,.135,.088,0),(.78,.153,.10,0),(.85,.139,.102,0),(.94,.146,.10,0),(1.0,.163,.104,0),(1.05,.176,.105,0),(1.10,.183,.100,0),(1.135,.168,.092,0),(1.155,.134,.080,0),(1.170,.098,.068,0),(1.182,.074,.056,0)],
       'default':[(.72,.135,.088,0),(.78,.153,.10,0),(.85,.139,.102,0),(.94,.146,.10,0),(1.0,.165,.104,0),(1.05,.180,.106,0),(1.10,.192,.102,0),(1.135,.186,.096,0),(1.155,.165,.088,0),(1.170,.124,.074,0),(1.182,.088,.058,0)]}
loft('Tunic body',TUNIC.get(KIND,TUNIC['default']),'Green' if KIND=='wind' else ('Ivory' if KIND in ['ice','lightning'] else 'Dark'),torso,40,.018)
for s,sg in [('l',1),('r',-1)]:
    lw=legweight(s);aw=armweight(s)
    # Slightly ballooned trousers, enough rings at knee for skinning.
    if KIND=='wind':
        # Knee-length balloon trousers, bare shins and long socks (approved sheet).
        pts=[(sg*.09,0,.75),(sg*.102,0,.70),(sg*.12,0,.60),(sg*.13,-.01,.50),(sg*.135,-.012,.42),(sg*.138,-.008,.385)]
        rr=[(.08,.077),(.10,.088),(.108,.090),(.110,.092),(.100,.086),(.066,.060)]
        tube('Trousers '+s,pts,rr,'Dark',lw,28)
        tube('Knee cuff '+s,[(sg*.138,-.008,.392),(sg*.139,-.006,.360)],[(.065,.060),(.063,.058)],'Dark',lw,24)
        tube('Shin '+s,[(sg*.139,-.006,.37),(sg*.14,-.003,.30),(sg*.14,0,.24)],[.037,.035,.032],'Skin',lw,20)
        tube('Sock '+s,[(sg*.14,0,.262),(sg*.14,0,.14)],.041,'Green',lw,20)
    else:
        OUTFIT.build_trousers(globals(),KIND,s,sg)
        tube('Sock '+s,[(sg*.14,0,.23),(sg*.14,0,.13)],.042,accent,lw,20)
    # Round 9: the bare arms are built after apply_proportions along the
    # re-posed bones (OUTFIT.build_arms_final); the shirt shoulder stays here.
    if KIND=='fire':
        ell('Shoulder '+s,(sg*.185,0,1.125),(.056,.054,.052),'Ivory',aw)
    # Palm follows hand bone (round 9: tilted along it, it used to hang straight
    # down and looked broken at the wrist); fingers have separate phalanges.
    ob=ell('Palm '+s,(sg*.497,-.012,.77),(.036,.019,.051),'Skin','hand_'+s)
    Rp=Matrix.Rotation(-sg*math.radians(27),3,'Y');pc=Vector((sg*.497,-.012,.77))
    for v in ob.data.vertices:v.co=pc+Rp@(v.co-pc)
    for nm in ['index','middle','ring','pinky','thumb']:
        a,b,_=bones[nm+'_01_'+s];_,c,_=bones[nm+'_02_'+s]
        def fw(p,a=a,b=b,c=c,nm=nm,s=s):
            t=max(0,min(1,(p-a).dot(c-a)/(c-a).length_squared));v=max(0,min(1,(t-.3)/.4))
            return {nm+'_01_'+s:1-v,nm+'_02_'+s:v}
        tube(nm+' '+s,[a,a.lerp(b,.5),b,b.lerp(c,.6),c],[.010,.010,.009,.008,.004],'Skin',fw,10)
    # Shoes (round 8): chunky high-top sneakers / lace-up boots with thick soles.
    OUTFIT.build_shoe(globals(),KIND,s,sg)
    top=OUTFIT.SHOES[KIND]['top']
    if KIND=='fire':
        # Fold-over red cuff with gold trim and a gold diamond at the front.
        tube('Boot cuff '+s,[(sg*.14,.010,top-.040),(sg*.14,.010,top+.014)],[(.069,.064),(.071,.066)],'Red',lw,24)
        tube('Boot cuff trim '+s,[(sg*.14,.010,top-.044),(sg*.14,.010,top-.036)],[(.072,.067),(.072,.067)],'Gold',lw,24)
        ell('Boot diamond',(sg*.14,-.068,top-.012),(.016,.005,.021),'Gold',lw,4,3)

def panel(name,a0,a1,z0,z1,rx0,ry0,rx1,ry1,material,w,steps=12,lining=None):
    vs=[];fs=[]
    for i in range(10):
        t=i/9;z=z0*(1-t)+z1*t
        for j in range(steps+1):
            u=j/steps;a=a0+(a1-a0)*u;r=1+.022*sin(u*pi*6)*t
            rx=rx0*(1-t)+rx1*t;ry=ry0*(1-t)+ry1*t
            if name.startswith(('Layered robe','Athletic split wrap')):
                rx=.160*(1-t)+rx1*t+.032*sin(pi*min(1,t*2))
                ry=.119*(1-t)+ry1*t+.005*sin(pi*min(1,t*2))
            vs.append((rx*cos(a)*r,ry*sin(a)*r,z-.025*sin(pi*u)*t))
    for i in range(9):
        for j in range(steps):a=i*(steps+1)+j;fs.append((a,a+steps+1,a+steps+2,a+1))
    ob=mesh(name,vs,fs,material,w)
    bpy.context.view_layer.objects.active=ob
    sol=ob.modifiers.new('Fabric thickness','SOLIDIFY');sol.thickness=.004
    if lining:
        ob.data.materials.append(mats[lining]);sol.material_offset=1
    bpy.ops.object.modifier_apply(modifier=sol.name)
    # Weight generated inner vertices like outer vertices.
    for vg in list(ob.vertex_groups):ob.vertex_groups.remove(vg)
    weights(ob,w)
    for edge in [0,steps]:
        tube(name+' edge',[vs[i*(steps+1)+edge] for i in range(10)],.004,'Gold' if KIND=='fire' else 'Cream',w,6)
    tube(name+' hem',vs[-(steps+1):],.005,'Gold' if KIND=='fire' else 'Cream',w,6)
    return ob
def star(name,x,y,z,size,material,w,points=4):
    vs=[(x,y-.002,z)]
    for i in range(points*2):
        a=pi/2+i*pi/points;r=size if i%2==0 else size*.31
        vs.append((x+r*cos(a),y,z+r*sin(a)))
    fs=[(0,i+1,(i+1)%(points*2)+1) for i in range(points*2)]
    ob=mesh(name,vs,fs,material,w)
    sol=ob.modifiers.new('Emboss','SOLIDIFY');sol.thickness=.002
    bpy.context.view_layer.objects.active=ob;bpy.ops.object.modifier_apply(modifier=sol.name)
    return ob
def ribbon(name,points,width,material,w):
    vs=[];fs=[]
    for i,p in enumerate(points):
        vs.extend([(p[0]-width/2,p[1],p[2]),(p[0]+width/2,p[1],p[2])])
        if i:fs.append((2*i-2,2*i-1,2*i+1,2*i))
    return mesh(name,vs,fs,material,w)
def tassel(x,y,z,color,w):
    ell('Tassel bead',(x,y,z),(.013,.012,.015),'Gold',w,12,8)
    for j in range(7):
        a=2*pi*j/7
        tube('Tassel thread',[(x,y,z-.009),(x+.009*cos(a),y+.009*sin(a),z-.044),(x+.010*cos(a),y+.010*sin(a),z-.075)],[.003,.003,.0015],color,w,5)

if KIND=='fire':
    # Open long coat (round 8): red facings turning into pointed tails, red V
    # on the back, pointed red shoulder caps, scarf with one long tail.
    OUTFIT.fire_coat(globals())
    OUTFIT.fire_pauldrons(globals())
    OUTFIT.fire_scarf(globals())
    loft('Raised collar',[(1.125,.083,.06,0),(1.18,.105,.075,.01),(1.235,.153,.08,.016)],'Cream','neck_01',40,0,False)
    # Soft scarf wrapped around the neck (3d-v2 sheet): a puffy fabric band, not a tube.
    loft('Scarf neck',[(1.125,.090,.082,-.012),(1.145,.100,.092,-.016),(1.170,.102,.094,-.017),(1.195,.096,.088,-.014),(1.212,.084,.077,-.010)],'Red','neck_01',36,.035,False)
elif KIND=='ice':
    # Robe skirt with a handkerchief hem and lavender border (round 8), blue
    # sash with long ends, cords with tassels, kimono-like trims, neck scarf.
    _robe,_robe_at=OUTFIT.ice_robe(globals())
    OUTFIT.ice_wrap_lines(globals())
    loft('Soft tall cowl',[(1.12,.09,.082,0),(1.14,.117,.108,-.01),(1.18,.112,.102,-.008),(1.22,.098,.084,0)],'Ivory','neck_01',40,.05,False)
    # Soft wide brim: gentle cloth waves and a slight droop toward its edge.
    vs=[];fs=[];N=96;RB=9
    for i in range(RB):
        u=i/(RB-1);r=.17+.31*u
        for j in range(N):
            a=2*pi*j/N
            z=1.618-.050*u*u-.055*u*u*cos(a)**2+.020*sin(3*a+.6)*u*u+.010*sin(5*a+2.0)*u**3+.012*sin(a+1)*u
            vs.append((r*cos(a),r*.80*sin(a)+.024,z))
    for i in range(RB-1):
        for j in range(N):a=i*N+j;b2=i*N+(j+1)%N;fs.append((a,a+N,b2+N,b2))
    ob=mesh('Wide hat brim',vs,fs,'Ivory','head')
    bpy.context.view_layer.objects.active=ob;m=ob.modifiers.new('Brim thickness','SOLIDIFY');m.thickness=.009;bpy.ops.object.modifier_apply(modifier=m.name)
    tube('Hat brim edge',vs[-N:]+[vs[-N]],.005,'Cream','head',8)
    # Crown: soft wrinkled cone; the tip bends back and falls to the right.
    hatpath=bez([(0,.030,1.600),(-.006,.045,1.870),(-.125,.072,1.945),(-.225,.105,1.805)],48)
    vs=[];fs=[];N=40;M=len(hatpath)
    for i,p0 in enumerate(hatpath):
        s=i/(M-1);p0=Vector(p0)
        tg=(Vector(hatpath[min(i+1,M-1)])-Vector(hatpath[max(i-1,0)])).normalized()
        ax=tg.cross(Vector((0,1,0)));ax=ax.normalized() if ax.length>1e-6 else Vector((1,0,0))
        ay=tg.cross(ax).normalized()
        base=(1-s)**1.15
        for j in range(N):
            a=2*pi*j/N
            wr=1+.045*sin(5*a+7*s)*sin(pi*min(1,s*1.4))+.025*sin(3*a+2+11*s)
            rx=(.200*base+.004)*wr;ry=(.168*base+.004)*wr
            vs.append(p0+ax*(rx*cos(a))+ay*(ry*sin(a)))
    for i in range(M-1):
        for j in range(N):a=i*N+j;b2=i*N+(j+1)%N;fs.append((a,b2,b2+N,a+N))
    fs.append(tuple(range(N-1,-1,-1)));fs.append(tuple((M-1)*N+j for j in range(N)))
    mesh('Bent hat crown',vs,fs,'Ivory','head')
    # Wide soft scarf band with a knot and a gold ring (round 9), tassel at the tip.
    OUTFIT.ice_hat_band(globals())
    tassel(-.225,.105,1.800,'Lavender','head')
elif KIND=='wind':
    OUTFIT.wind_wrap(globals())   # round 8: cream borders, waist roll, belt ring
    tube('Tunic seam',[(0,-.108,.83),(0,-.110,1.05),(0,-.106,1.11),(0,-.094,1.15),(0,-.077,1.17),(0,-.061,1.183)],.0025,'Khaki',torso,6)
    tassel(.125,-.15,.775,'Khaki','pelvis')
else:
    # Oversized asymmetrical hoodie (round 8): purple straps, bolt and back
    # triangle; two straps per side hanging along the cargo joggers.
    OUTFIT.lightning_hoodie(globals())
    ell('Folded hood',(0,.101,1.126),(.130,.066,.095),'Ivory','spine_03')
    tube('Cowl drape',[(-.090,0,1.18),(-.102,-.084,1.16),(0,-.142,1.095),(.102,-.084,1.16),(.090,0,1.18)],.032,'Ivory','spine_03',18)
    OUTFIT.lightning_hip_straps(globals())
    OUTFIT.trouser_seat(globals(),'Purple')
    for sg in [-1,1]:
        lobe=EAR_LOBES['l' if sg>0 else 'r']
        star('Earring',lobe.x+sg*.004,lobe.y-.006,lobe.z-.034,.019,'Gold','head')
        tube('Earring link',[(lobe.x+sg*.003,lobe.y-.004,lobe.z-.002),(lobe.x+sg*.004,lobe.y-.006,lobe.z-.016)],.003,'Gold','head',8)

# Belts, buckle, pendant finish the silhouette.
if KIND=='ice':
    loft('Waist sash',[(.778,.222,.166,0),(.800,.220,.164,0),(.824,.216,.161,0)],'IcePants','pelvis',48,.02,False)
    OUTFIT.ice_sash_and_cords(globals(),_robe_at)
elif KIND!='lightning':
    loft('Waist belt',[(.78,.177,.137,0),(.80,.172,.134,0),(.822,.168,.131,0)],'Brown' if KIND=='fire' else 'Dark','pelvis',40,0,False)
    box('Belt buckle',(0,-.142,.802),(.056,.013,.045),'Gold','pelvis',.006)
    box('Buckle inset',(0,-.152,.802),(.034,.008,.025),'Brown' if KIND=='fire' else 'Dark','pelvis',.003)
    if KIND=='fire':
        ell('Belt charm',(.072,-.150,.748),(.013,.006,.022),'Gold','pelvis',4,3)
        tassel(.072,-.150,.718,'Red','pelvis')
if KIND in ['fire','wind']:
    tube('Pendant chain',[(-.07,-.083,1.16),(0,-.118,1.056),(.07,-.083,1.16)],.002,'Gold',torso,6)
    star('Pendant',0,-.121,1.05,.020,'Gold',torso)

# Seat the shortened head back onto the unchanged neck and collar.
for ob in parts:
    groups=[g.name for g in ob.vertex_groups]
    if groups and all(g=='head' or g.startswith(('face_','hair_')) for g in groups):
        for v in ob.data.vertices:v.co.z-=.035
        if ob.data.shape_keys:
            for kb in ob.data.shape_keys.key_blocks:
                for d in kb.data:d.co.z-=.035
for name,(h,t,parent) in list(bones.items()):
    if name=='head' or name.startswith(('face_','hair_')):
        bones[name]=(Vector(h)-Vector((0,0,.035)),Vector(t)-Vector((0,0,.035)),parent)
# Re-proportion to the approved sheets: smaller head, short neck, higher
# shoulders and waist, arms closer to the body (all parts and bones).
wizard_hair_v5.apply_proportions(globals())
OUTFIT.build_arms_final(globals())   # round 9: continuous bare arms on the re-posed bones
wizard_hair_v5.resolve_hair_cloth(globals())   # round 9: long hair stays outside the clothes
if KIND=='ice':
    OUTFIT.ice_staff(globals())   # round 11: she casts with a staff (bones 'staff', 'staff_tip')
HS=wizard_hair_v5.head_scale(KIND)
if HEAD_ONLY:
    # Look-development shortcut: head renders with body, collar and hat in
    # place, but no rig, animation or export.
    wizard_hair_v5.head_review(globals(),OUT/KIND/'head_review')
# Shared deformation rig, bone collections and readable custom properties.

bpy.ops.object.select_all(action='DESELECT')
ad=bpy.data.armatures.new('WizardHumanoid');rig=bpy.data.objects.new('SK_'+KIND.title()+'_Rig',ad);scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
for name,(h,t,parent) in bones.items():
    b=ad.edit_bones.new(name);b.head=h;b.tail=t
    if parent:b.parent=ad.edit_bones[parent]
    b.use_deform=True
bpy.ops.object.mode_set(mode='OBJECT');rig.show_in_front=True;ad.display_type='OCTAHEDRAL'
for label,prefixes in [('Body',('root','pelvis','spine','neck','head','clavicle','upperarm','lowerarm','hand','thigh','calf','foot','ball')),('Fingers',('index','middle','ring','pinky','thumb')),('Cloth and hair',('cloth','hair','scarf','acc_')),('Face',('face_',))]:
    co=ad.collections.new(label)
    for b in ad.bones:
        if b.name.startswith(prefixes):co.assign(b)
CHAINS=globals().get('HAIR_CHAINS') or []
ACC=globals().get('ACC_CHAINS') or []   # round 9: straps, cords, sash ends
rig['accessory_chains']=', '.join(c['bone_names'][0] for c in ACC) or 'none'
rig['asset_version']='5.2';rig['hair_chains']=', '.join(c['bone_names'][0] for c in CHAINS) or 'none (hair follows the head)';rig['forward']='-Y in Blender; +X in Unreal import';rig['description']='Shared FK deform rig. A-pose reference. Accessory bones are optional animation controls.'
for ob in parts:
    mod=ob.modifiers.new('Wizard skin','ARMATURE');mod.object=rig;ob.parent=rig
    # Consistent geometric UVs for every editable part.
    if not ob.data.uv_layers:
        uv=ob.data.uv_layers.new(name='UVMap')
        for poly in ob.data.polygons:
            axis=max(range(3),key=lambda k:abs(poly.normal[k]));axes=[k for k in range(3) if k!=axis]
            for li in poly.loop_indices:
                p=ob.data.vertices[ob.data.loops[li].vertex_index].co
                uv.data[li].uv=(p[axes[0]]*.5+.5,p[axes[1]]*.5)
# Round 10: fabric weave, fine wrinkles and small prints (texture + 'Detail' colours + 'DetailUV').
import wizard_fabric_v5
FABRIC=wizard_fabric_v5.fabric_detail(globals())
for ob in parts:
    if ob.data.uv_layers.get('UVMap'):ob.data.uv_layers.active=ob.data.uv_layers['UVMap']

def resetpose():
    for p in rig.pose.bones:p.rotation_mode='XYZ';p.rotation_euler=(0,0,0);p.location=(0,0,0);p.scale=(1,1,1)
def keypose(frame):
    for p in rig.pose.bones:
        p.keyframe_insert('rotation_euler',frame=frame,group=p.name)
        if p.name=='pelvis' or p.name.startswith('face_'):
            p.keyframe_insert('location',frame=frame,group=p.name)
            p.keyframe_insert('scale',frame=frame,group=p.name)
def rot(name,x=0,y=0,z=0):rig.pose.bones[name].rotation_euler=(math.radians(x),math.radians(y),math.radians(z))
actions=[]
ACTIONS=[('Idle',61),('Walk',25),('Cast',31),('Guard',31),('JointCheck',61),('FaceCheck',91)]
if CHAINS or ACC:ACTIONS.append(('HairCheck',61))   # swings every hair and accessory chain (weights / Unreal physics setup)
for actionname,end in ACTIONS:
    rig.animation_data_create();act=bpy.data.actions.new(KIND.title()+'_'+actionname);rig.animation_data.action=act;act.use_fake_user=True;actions.append(act)
    frames=[1,end//2,end] if actionname=='Idle' else ([1,7,13,19,25] if actionname=='Walk' else [1,9,19,end])
    if actionname=='FaceCheck':frames=[1,10,18,26,36,46,56,66,76,91]
    if actionname=='HairCheck':frames=[1,16,31,46,61]
    for fi,fr in enumerate(frames):
        resetpose();t=(fr-1)/(end-1)
        if actionname=='FaceCheck':
            # Bones for gaze / brows / smile; blink (10-18) and the open mouth
            # (66-76) are the morph targets Blink and A (keyed below).
            if fr in [36,46]:
                for side in ['l','r']:
                    gaze=rig.pose.bones['face_gaze_'+side]
                    gaze.location=gaze.bone.matrix_local.to_3x3().inverted() @ (Vector((.011,-.008,0))*HS)
                    rig.pose.bones['face_brow_'+side].location.y=.012*HS
            if fr in [66,76]:
                for side in ['l','r']:
                    rig.pose.bones['face_smile_'+side].location.y=.009*HS
                    rig.pose.bones['face_cheek_'+side].location.y=.005*HS
        elif actionname=='HairCheck':
            # every chain bone bends a little: forward/back at 16 and 46, sideways at 31
            ax,az={16:(1,0),31:(0,1),46:(-1,0)}.get(fr,(0,0))
            for c in CHAINS+ACC:
                a=48.0/len(c['bone_names'])          # about 48 degrees over the whole chain
                for nm in c['bone_names']:rot(nm,ax*a,0,az*a)
            rot('head',0,0,{31:6}.get(fr,0))
        elif actionname=='Idle':
            rot('spine_02',sin(t*pi)*1.3);rot('head',0,sin(t*pi)*2,0)
            for s,sg in [('l',1),('r',-1)]:rot('upperarm_'+s,0,0,sg*2*sin(t*pi))
        elif actionname=='Walk':
            for s,sg in [('l',1),('r',-1)]:
                a=sin(t*2*pi)*sg;rot('thigh_'+s,23*a);rot('calf_'+s,-max(0,a)*30);rot('upperarm_'+s,-16*a);rot('lowerarm_'+s,-8)
                rot('cloth_front_01_'+s,max(0,a)*15);rot('cloth_back_01_'+s,min(0,a)*15)
            rig.pose.bones['pelvis'].location.z=.012*(1-cos(t*4*pi))
        elif actionname in ['Cast','Guard','JointCheck']:
            strength=sin(pi*t)
            for s,sg in [('l',1),('r',-1)]:
                rot('upperarm_'+s,-42*strength,0,-sg*26*strength)
                rot('lowerarm_'+s,-64*strength,0,sg*8*strength)
                for nm in ['index','middle','ring','pinky']:
                    rot(nm+'_01_'+s,25*strength);rot(nm+'_02_'+s,35*strength)
            rot('spine_02',8*strength);rot('head',-8*strength)
            if actionname=='JointCheck':
                rot('thigh_l',-30*strength);rot('calf_l',45*strength);rot('foot_l',-15*strength)
                rot('cloth_front_01_l',-38*strength);rot('cloth_front_02_l',5*strength);rot('cloth_back_01_l',-18*strength)
        keypose(fr)
    act['purpose']='Preview / deformation test, not a replacement for final gameplay animation'
rig.animation_data.action=None;resetpose();scene.frame_set(1);scene.render.fps=30;scene.frame_end=61
# FaceCheck morph keys (Blink at 10-18, A at 66-76).  The actions are stored,
# not assigned, so other clips and renders show the neutral face; the
# validation assigns them and the FaceCheck FBX carries them as curves.
MORPH_ON={'Blink':(10,18),'A':(66,76)}
def key_morphs(ob,name):
    sk=ob.data.shape_keys
    if not sk:return None
    for kb in sk.key_blocks[1:]:
        if kb.name not in MORPH_ON:continue
        for fr in [1,10,18,26,36,46,56,66,76,91]:
            kb.value=1.0 if fr in MORPH_ON[kb.name] else 0.0
            kb.keyframe_insert('value',frame=fr)
        kb.value=0.0
    ad=sk.animation_data
    if ad and ad.action:
        ad.action.name=name;ad.action.use_fake_user=True;ad.action['key_owner']=ob.name;ad.action=None
    return name
for ob in parts:
    if ob.data.shape_keys:key_morphs(ob,KIND.title()+'_FaceCheck_Morphs | '+ob.name)

# Validation before packaging.
report={'character':KIND,'bones':len(bones),'hair_chains':{c['bone_names'][0][:-3]:len(c['bone_names']) for c in CHAINS},'accessory_chains':{c['bone_names'][0][:-3]:len(c['bone_names']) for c in ACC},'parts':len(parts),'vertices':sum(len(o.data.vertices) for o in parts),'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in parts),'unweighted_vertices':0,'invalid_weights':0,'actions':[a.name for a in actions]}
report['fabric']=FABRIC
for ob in parts:
    for v in ob.data.vertices:
        sm=sum(g.weight for g in v.groups)
        report['unweighted_vertices']+=int(sm<.001);report['invalid_weights']+=int(abs(sm-1)>.015)
assert report['unweighted_vertices']==0,report
assert report['invalid_weights']==0,report

# Render studio (excluded from FBX selection).
def aim(ob,p):ob.rotation_euler=(Vector(p)-ob.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(2.6,-6,2.6));cam=bpy.context.object;cam.name='Presentation Camera';aim(cam,(0,0,.91));cam.data.type='ORTHO';cam.data.ortho_scale=2.28;scene.camera=cam

bpy.ops.mesh.primitive_plane_add(size=200);floor=bpy.context.object;floor.name='Studio ground';floor.data.materials.append(mat('Studio',(.115,.135,.16)))
wizard_hair_v5.studio_light(scene)
scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True
scene.render.resolution_x=1000;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
# Save editable source with all pieces and clean A-pose.
folder=OUT/KIND;folder.mkdir(exist_ok=True)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_distance=2.8;area.spaces.active.region_3d.view_location=(0,0,.95)
            area.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion();area.spaces.active.shading.type='MATERIAL'
scene['README']='V5 head: hair, scalp, ears, face shape, eyes and brows are generated by wizard_hair_v5.py (edit STYLES["'+KIND+'"] there and rerun build_wizard_models_v5.py -- '+KIND+'). Morph targets (shape keys, as in VRM / VRoid): Blink, Blink_L, Blink_R close the eyes, A opens the mouth. Facial bones: face_gaze local X/Y for eye direction; face_brow / face_smile / face_cheek local X/Y for expression. FaceCheck clip demonstrates these (its morph keys are stored in the actions <Kind>_FaceCheck_Morphs | <part>). Editable original pieces. Select rig > Pose Mode to move limbs. Actions include Idle, Walk, Cast, Guard and JointCheck'+(' plus HairCheck (bends every hair chain hair_<group>_NN and accessory chain acc_<name>_NN; set these chains up as AnimDynamics / Kawaii Physics chains in Unreal)' if CHAINS or ACC else '')+'. FBX exports are in the same folder. Custom skeleton requires retargeting for UE mannequin animations.'
bpy.ops.wm.save_as_mainfile(filepath=str(folder/(KIND+'_source.blend')))
if 'preview' in sys.argv:
    scene.cycles.samples=24;scene.render.resolution_x=800;scene.render.resolution_y=800
    for label,loc in [('head_front',(0,-4,1.45)),('head_side',(4,0,1.45)),('head_back',(0,4,1.45))]:
        cam.location=loc;aim(cam,(0,0,1.46));cam.data.ortho_scale=.69
        scene.render.filepath=str(folder/(label+'.png'));bpy.ops.render.render(write_still=True)
    print('V4_PREVIEW_COMPLETE',KIND)
    sys.exit(0)
scene.render.filepath=str(folder/(KIND+'_beauty.png'));bpy.ops.render.render(write_still=True)
cam.location=(.18,-4,1.43);aim(cam,(0,0,1.46));cam.data.ortho_scale=.69
scene.render.resolution_x=1000;scene.render.resolution_y=1000
scene.render.filepath=str(folder/(KIND+'_face.png'));bpy.ops.render.render(write_still=True)
# Technical three-view images rendered from the actual mesh.
scene.render.resolution_x=760;scene.render.resolution_y=960
for label,loc in [('front',(0,-6,.95)),('side',(6,0,.95)),('back',(0,6,.95))]:
    cam.location=loc;aim(cam,(0,0,.95));cam.data.ortho_scale=2.2
    scene.render.filepath=str(folder/(KIND+'_'+label+'.png'));bpy.ops.render.render(write_still=True)

# Game atlas keeps flat material colours only: bake scalp/undercut/blush to slots.
wizard_hair_v5.bake_scalp_to_material_slots(globals())
# Consolidated export mesh: one skeletal mesh, material slots retained.
bpy.ops.object.select_all(action='DESELECT')
for ob in parts:ob.select_set(True)
bpy.context.view_layer.objects.active=parts[0];bpy.ops.object.join();exportmesh=bpy.context.object;exportmesh.name='SK_'+KIND.title()
for kb in (exportmesh.data.shape_keys.key_blocks if exportmesh.data.shape_keys else []):kb.value=0.0
report['morph_targets']=[kb.name for kb in exportmesh.data.shape_keys.key_blocks[1:]] if exportmesh.data.shape_keys else []
GAME_MORPHS=key_morphs(exportmesh,KIND.title()+'_FaceCheck_Morphs')
# One portable PBR atlas material. UV0 is a tiled color/material atlas;
# the source .blend retains individual materials for easy art iteration.
import numpy as np
texdir=folder/'Textures';texdir.mkdir(exist_ok=True)
allmats=list(exportmesh.data.materials)
keep=[m for m in allmats if m.get('keep_texture')]   # hair cards keep their strand texture (alpha)
used=[m for m in allmats if not m.get('keep_texture')];slot={m.name:i for i,m in enumerate(used)}
tile=128;cols=8;rows=math.ceil(len(used)/cols)
sizeX=cols*tile;sizeY=rows*tile
base=np.zeros((sizeY,sizeX,4),dtype=np.float32);orm=np.ones_like(base)
yy,xx=np.mgrid[0:tile,0:tile];rng=np.random.default_rng(918)
grain=rng.uniform(-.010,.010,(tile,tile))+.004*np.sin(xx*pi)*np.sin(yy*pi)
for i,m in enumerate(used):
    x=(i%cols)*tile;y=(i//cols)*tile;p=m.node_tree.nodes.get('Principled BSDF');c=np.array(p.inputs['Base Color'].default_value[:3])
    iscloth=any(k in m.name for k in ['Cream','Ivory','Dark','Red','Purple','Lavender','Green','Khaki'])
    base[y:y+tile,x:x+tile,:3]=np.clip(c[None,None,:]*(1+grain[:,:,None]*(2 if iscloth else .2)),0,1)
    base[y:y+tile,x:x+tile,3]=1
    orm[y:y+tile,x:x+tile,1]=p.inputs['Roughness'].default_value
    orm[y:y+tile,x:x+tile,2]=p.inputs['Metallic'].default_value
def saveimage(name,pixels,colorspace):
    if colorspace=='sRGB':
        pixels=pixels.copy();rgb=pixels[:,:,:3];pixels[:,:,:3]=np.where(rgb<=.0031308,rgb*12.92,1.055*np.power(rgb,1/2.4)-.055)
    im=bpy.data.images.new(name,width=sizeX,height=sizeY,alpha=True)
    im.colorspace_settings.name=colorspace;im.pixels.foreach_set(pixels.ravel());im.filepath_raw=str(texdir/(name+'.png'));im.file_format='PNG';im.save();im.pack();return im
bc=saveimage('T_'+KIND.title()+'_BaseColor',base,'sRGB');rm=saveimage('T_'+KIND.title()+'_ORM',orm,'Non-Color')
exportmesh.data.uv_layers.active=exportmesh.data.uv_layers['UVMap']   # the atlas UVs (DetailUV stays as is)
if exportmesh.data.color_attributes.get('Scalp'):exportmesh.data.color_attributes.remove(exportmesh.data.color_attributes['Scalp'])   # baked into slots above
if exportmesh.data.color_attributes.get('Detail'):exportmesh.data.color_attributes.active_color=exportmesh.data.color_attributes['Detail']
uv=exportmesh.data.uv_layers.active
for p in exportmesh.data.polygons:
    m=allmats[p.material_index]
    if m.get('keep_texture'):
        p.material_index=1+keep.index(m);continue
    index=slot[m.name];cx=index%cols;cy=index//cols
    for li in p.loop_indices:
        old=uv.data[li].uv.copy();uv.data[li].uv=((cx+.04+.92*(old.x%1))/cols,(cy+.04+.92*(old.y%1))/rows)
    p.material_index=0
atlas=bpy.data.materials.new('M_'+KIND.title()+'_Atlas');atlas.use_nodes=True
nd=atlas.node_tree.nodes;lk=atlas.node_tree.links;pr=nd.get('Principled BSDF');a=nd.new('ShaderNodeTexImage');a.image=bc;a.location=(-600,200);lk.new(a.outputs['Color'],pr.inputs['Base Color'])
b=nd.new('ShaderNodeTexImage');b.image=rm;b.location=(-600,-100);sep=nd.new('ShaderNodeSeparateColor');sep.location=(-350,-100);lk.new(b.outputs['Color'],sep.inputs['Color']);lk.new(sep.outputs['Green'],pr.inputs['Roughness']);lk.new(sep.outputs['Blue'],pr.inputs['Metallic'])
# materials.clear() also zeroes every face's material index: keep them (the hair
# cards point at their own slots, round 9 -- they had come out on the atlas)
faceidx=[p.material_index for p in exportmesh.data.polygons]
exportmesh.data.materials.clear();exportmesh.data.materials.append(atlas)
for m in keep:exportmesh.data.materials.append(m)
exportmesh.data.polygons.foreach_set('material_index',faceidx);exportmesh.data.update()
report['game_material_slots']=1+len(keep);report['texture_size']=[sizeX,sizeY]
# Transform all geometry to centimetres only through FBX unit metadata, not baked object scale.
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);exportmesh.select_set(True);bpy.context.view_layer.objects.active=rig
def export_units(factor):
    # Bake centimetres into mesh/rest bones with unit object scales. This avoids
    # Unreal's default disabled Convert Scene Unit option producing 1.7cm people.
    for v in exportmesh.data.vertices:v.co*=factor
    if exportmesh.data.shape_keys:
        for kb in exportmesh.data.shape_keys.key_blocks:
            for d in kb.data:d.co*=factor
    rig.data.transform(Matrix.Scale(factor,4))
    for action in actions:
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        if curve.data_path.endswith('location'):
                            for key in curve.keyframe_points:
                                key.co.y*=factor;key.handle_left.y*=factor;key.handle_right.y*=factor
export_units(100);scene.unit_settings.scale_length=.01
saved_rig_name=rig.name;rig.name='Armature'
args=dict(use_selection=True,object_types={'ARMATURE','MESH'},apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Y',axis_up='Z',add_leaf_bones=False,use_armature_deform_only=True,mesh_smooth_type='FACE',use_mesh_modifiers=True,bake_anim=False,path_mode='COPY',embed_textures=True,colors_type='LINEAR')
bpy.ops.export_scene.fbx(filepath=str(folder/('SK_'+KIND.title()+'.fbx')),**args)
# Export animations separately so Unreal creates a single mesh/skeleton.
for act in actions:
    rig.animation_data.action=act;scene.frame_start=1;scene.frame_end=int(act.frame_range[1]);scene.frame_set(1)
    bpy.ops.object.select_all(action='DESELECT');rig.select_set(True)
    aa=dict(args);aa.update(bake_anim=True,bake_anim_use_all_actions=False,bake_anim_use_nla_strips=False,bake_anim_simplify_factor=0.0)
    morphs=act.name.endswith('_FaceCheck') and GAME_MORPHS
    if morphs:
        exportmesh.select_set(True);sk=exportmesh.data.shape_keys
        sk.animation_data_create();sk.animation_data.action=bpy.data.actions[GAME_MORPHS]
        if sk.animation_data.action_slot is None and len(bpy.data.actions[GAME_MORPHS].slots):sk.animation_data.action_slot=bpy.data.actions[GAME_MORPHS].slots[0]
        aa.update(embed_textures=False,path_mode='STRIP')
    bpy.ops.export_scene.fbx(filepath=str(folder/('A_'+act.name+'.fbx')),**aa)
    if morphs:
        exportmesh.data.shape_keys.animation_data.action=None
        for kb in exportmesh.data.shape_keys.key_blocks:kb.value=0.0
export_units(.01);scene.unit_settings.scale_length=1.0
rig.name=saved_rig_name
rig.animation_data.action=next(a for a in actions if a.name.endswith('_JointCheck'));scene.frame_start=1;scene.frame_end=61;scene.frame_set(19)
cam.location=(2.6,-6,2.6);aim(cam,(0,0,.91));cam.data.ortho_scale=2.28
scene.render.resolution_x=1000;scene.render.resolution_y=1100;scene.render.filepath=str(folder/(KIND+'_pose_test.png'));bpy.ops.render.render(write_still=True)
rig.animation_data.action=None;resetpose();scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(folder/(KIND+'_game.blend')))
(folder/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('WIZARD_BUILD_COMPLETE',json.dumps(report))
