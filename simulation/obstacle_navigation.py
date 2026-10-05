"""Known-map simulation route planner and footprint guard; no camera/LLM input."""
import heapq
import math

RADIUS = .16  # Conservative disk enclosing tracks and forward launcher.
MARGIN = .03
PLANNING_MARGIN = .05  # Extra room for waypoint/heading tracking error.
GRID = .05
BOUNDS = (-.4, 2., -1., 1.)
PRESETS = ('clear', 'block', 'left_open', 'right_open', 'wall', 'blocked')


def preset(name):
    if name not in PRESETS:
        raise ValueError('Unknown obstacle scene')
    block = dict(x=.55, y=0., hx=.09, hy=.18)
    if name == 'clear': return []
    if name == 'block': return [block]
    if name == 'left_open': return [dict(x=.55,y=-.42,hx=.09,hy=.62)]
    if name == 'right_open': return [dict(x=.55,y=.42,hx=.09,hy=.62)]
    if name == 'wall': return [dict(x=.6,y=0.,hx=.04,hy=.42)]
    return [dict(x=.25,y=0.,hx=.025,hy=.3),
            dict(x=-.25,y=0.,hx=.025,hy=.3),
            dict(x=0.,y=.25,hx=.3,hy=.025),
            dict(x=0.,y=-.25,hx=.3,hy=.025)]


def clearance(x,y,obstacles):
    return min((math.hypot(max(abs(x-o['x'])-o['hx'],0),
                           max(abs(y-o['y'])-o['hy'],0))-RADIUS
                for o in obstacles), default=math.inf)


def safe(x,y,obstacles,margin=MARGIN):
    return clearance(x,y,obstacles) >= margin-1e-9


def segment_safe(a,b,obstacles,margin=MARGIN):
    n=max(1,math.ceil(math.dist(a,b)/(.01)))
    return all(safe(a[0]+(b[0]-a[0])*i/n,a[1]+(b[1]-a[1])*i/n,obstacles,margin)
               for i in range(n+1))


def route(start,goal,obstacles):
    """A* with inflated obstacles and checked edges, including endpoint edges."""
    xmin,xmax,ymin,ymax=BOUNDS
    if not all(math.isfinite(v) for v in (*start,*goal)):
        raise ValueError('Finite route coordinates required')
    if not safe(*start,obstacles) or not safe(*goal,obstacles):return None
    def key(p):return (round((p[0]-xmin)/GRID),round((p[1]-ymin)/GRID))
    def point(k):return (xmin+k[0]*GRID,ymin+k[1]*GRID)
    def valid(k):
        x,y=point(k)
        return xmin<=x<=xmax and ymin<=y<=ymax and safe(x,y,obstacles,PLANNING_MARGIN)
    source,target=key(start),key(goal)
    if not valid(source) or not valid(target):return None
    if not segment_safe(start,point(source),obstacles) or not segment_safe(point(target),goal,obstacles):return None
    queue=[(0,source)];cost={source:0};parent={}
    while queue:
        _,current=heapq.heappop(queue)
        if current==target:
            path=[goal,point(current)]
            while current!=source:
                current=parent[current];path.append(point(current))
            path.append(start);path.reverse()
            # Shortcut only along independently checked collision-free segments.
            simplified=[path[0]];i=0
            while i<len(path)-1:
                j=len(path)-1
                while j>i+1 and not segment_safe(path[i],path[j],obstacles,PLANNING_MARGIN):j-=1
                simplified.append(path[j]);i=j
            return simplified
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            nxt=(current[0]+dx,current[1]+dy)
            if not valid(nxt) or not segment_safe(point(current),point(nxt),obstacles,PLANNING_MARGIN):continue
            new=cost[current]+math.hypot(dx,dy)*GRID
            if new<cost.get(nxt,math.inf):
                cost[nxt]=new;parent[nxt]=current
                heapq.heappush(queue,(new+math.dist(point(nxt),point(target)),nxt))
    return None


def ranges(x,y,heading,obstacles,max_range=2.5):
    """Ideal horizontal laser fan, measured from disk edge; rectangles only."""
    output={}
    for angle in (0,45,90,135,180,-135,-90,-45):
        theta=heading+math.radians(angle);dx,dy=math.cos(theta),math.sin(theta)
        nearest=max_range
        for o in obstacles:
            lo,hi=0.,math.inf
            for origin,direction,center,half in ((x,dx,o['x'],o['hx']),(y,dy,o['y'],o['hy'])):
                if abs(direction)<1e-10:
                    if not center-half<=origin<=center+half:lo,hi=1.,0.;break
                else:
                    a,b=(center-half-origin)/direction,(center+half-origin)/direction
                    lo=max(lo,min(a,b));hi=min(hi,max(a,b))
            if hi>=lo:nearest=min(nearest,max(0.,lo-RADIUS))
        output[str(angle)]=round(nearest,3)
    return output
