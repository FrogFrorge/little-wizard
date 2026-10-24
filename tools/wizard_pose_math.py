import math,copy
def va(a,b):return [x+y for x,y in zip(a,b)]
def vs(a,b):return [x-y for x,y in zip(a,b)]
def vm(a,s):return [x*s for x in a]
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def length(a):return math.sqrt(dot(a,a))
def norm(a):return vm(a,1/max(length(a),1e-9))
def qm(a,b):
 x,y,z,w=a;X,Y,Z,W=b
 return [w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z]
def qi(q):return [-q[0],-q[1],-q[2],q[3]]
def qr(q,v):return qm(qm(q,v+[0]),qi(q))[:3]
def axis(a,deg):
 s=math.sin(math.radians(deg)/2);return vm(norm(a),s)+[math.cos(math.radians(deg)/2)]
def between(a,b):
 a,b=norm(a),norm(b);d=dot(a,b)
 if d<-.99999:return axis(cross(a,[0,0,1] if abs(a[2])<.9 else [0,1,0]),180)
 q=cross(a,b)+[1+d];return vm(q,1/max(length(q),1e-9))
def fk(p):
 out={}
 def bone(n):
  if n in out:return out[n]
  b=p[n];par=b['parent']
  if par not in p:out[n]=(b['p'][:],b['q'][:])
  else:
   pos,q=bone(par);out[n]=(va(pos,qr(q,b['p'])),qm(q,b['q']))
  return out[n]
 for n in p:bone(n)
 return out
def worldrot(p,n,q):
 world=fk(p);parent=p[n]['parent'];p[n]['q']=qm(qi(world[parent][1]),q) if parent in world else q
def rotate(p,n,a,deg):worldrot(p,n,qm(axis(a,deg),fk(p)[n][1]))
def ik(p,upper,lower,end,target,pole):
 w=fk(p);A=w[upper][0];B=w[lower][0];C=w[end][0];l1=length(vs(B,A));l2=length(vs(C,B));dvec=vs(target,A);d=min(max(length(dvec),abs(l1-l2)+.05),l1+l2-.1);direction=norm(dvec);target=va(A,vm(direction,d));v=vs(pole,A);side=norm(vs(v,vm(direction,dot(v,direction))));x=(l1*l1-l2*l2+d*d)/(2*d);h=math.sqrt(max(0,l1*l1-x*x));elbow=va(va(A,vm(direction,x)),vm(side,h))
 worldrot(p,upper,qm(between(vs(B,A),vs(elbow,A)),w[upper][1]));w=fk(p);worldrot(p,lower,qm(between(vs(w[end][0],w[lower][0]),vs(target,w[lower][0])),w[lower][1]))
def smooth(t):t=max(0,min(1,t));return t*t*(3-2*t)
def mix(a,b,t):return va(vm(a,1-t),vm(b,t))
def pose(base,kind,t):
 p=copy.deepcopy(base);rest=fk(base);pelvis=base['pelvis']['p'][:];weight=smooth(t/.12) if kind not in ['Hover','WindFlight'] else 1
 def arm(side,target,pole):
  n='hand_'+side;target=mix(rest[n][0],target,weight);ik(p,'upperarm_'+side,'lowerarm_'+side,n,target,pole)
 def legs(height=0,forward=0):
  for s,sign in [('l',1),('r',-1)]:
   foot=rest['foot_'+s][0][:];foot[1]+=forward;foot[2]+=height;ik(p,'thigh_'+s,'calf_'+s,'foot_'+s,foot,[sign*14,70,55])
 if kind=='Super_Fire':
  theta=2*math.pi*max(0,min(1,(t-.10)/.58));target=[-22+32*math.sin(theta),29,146+30*math.cos(theta)];release=smooth((t-.69)/.11)
  arm('r',mix(target,[-20,54,143],release),[-70,12,130]);arm('l',mix([23,28,126],[20,54,143],release),[65,8,118])
 elif kind=='Super_Ice':
  release=smooth((t-.70)/.10)
  arm('l',mix([-17,30,143],[70,10,147],release),[46,4,119]);arm('r',mix([17,37,137],[-70,10,147],release),[-46,8,118])
 elif kind=='Super_Wind':
  tuck=smooth(t/.20);p['pelvis']['p'][2]+=34*tuck;rotate(p,'spine_03',[1,0,0],-25*tuck)
  for s,sign in [('l',1),('r',-1)]:
   ik(p,'thigh_'+s,'calf_'+s,'foot_'+s,mix(rest['foot_'+s][0],[sign*13,26,90],tuck),[sign*16,85,105]);arm(s,[sign*18,47,110],[sign*47,34,132])
 elif kind=='Super_Lightning':
  slam=smooth((t-.61)/.19);recover=smooth((t-.84)/.16);amount=slam*(1-recover)
  p['pelvis']['p'][2]-=37*amount;rotate(p,'spine_02',[1,0,0],-20*amount);rotate(p,'spine_04',[1,0,0],-25*amount);legs()
  for s,sign in [('l',1),('r',-1)]:
   target=mix([sign*9,1,198],[sign*12,57,22],slam);target=mix(target,rest['hand_'+s][0],recover);arm(s,target,[sign*48,25,110])
 elif kind=='Hover':
  p['pelvis']['p'][2]+=3*math.sin(t*math.pi*2);legs(28,-12)
  for s,sign in [('l',1),('r',-1)]:arm(s,[sign*(61+2*math.sin(t*6.283)),7,116],[sign*53,-4,125])
 elif kind=='WindFlight':
  rotate(p,'pelvis',[1,0,0],-82)
  for s,sign in [('l',1),('r',-1)]:arm(s,[sign*18,98,106],[sign*26,60,98])
 # Keep IK markers aligned, so the mannequin's post-process rig does not undo the authored pose.
 world=fk(p)
 for ikn,src in [('ik_hand_l','hand_l'),('ik_hand_r','hand_r'),('ik_foot_l','foot_l'),('ik_foot_r','foot_r')]:
  if ikn not in p:continue
  parent=p[ikn]['parent'];pw,pq=world[parent];p[ikn]['p']=qr(qi(pq),vs(world[src][0],pw));p[ikn]['q']=qm(qi(pq),world[src][1])
 return p

