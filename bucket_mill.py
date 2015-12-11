from PIL import Image
from numpy import array,zeros,amax,int8,int16,int32,unique,roll,mgrid,ma,ones,sqrt,extract
from sys import argv
from math import radians,cos,sin,tan
from stl import mesh
integer = int32

directions = {"up":[0,-1],"down":[0,+1],"left":[-1,0],"right":[+1,0],"center":[0,0]}

def bit_pixels(bit_shape="cylinder",diameter=3):
    radius = diameter/2.0
    if diameter % 2:
        size = diameter
        x, y = mgrid[:size, :size]
        x = x + 0.5
        y = y + 0.5
    else:
        size = diameter + 1
        x, y = mgrid[:size, :size]
    sphere = (x - radius) ** 2 + (y - radius) ** 2
    circle_mask = ma.make_mask(sphere > radius**2) #true when outside the circle
    high = ones((size,size))*10000
    if bit_shape in ["cylinder","ball","sphere"]:
        if bit_shape == "cylinder":
            output = circle_mask * high
        else:
            #print "test"
            output = (circle_mask == False) * sphere + circle_mask * high
    elif bit_shape.startswith("v"):
        angle = float(bit_shape[1:])/2.0
        angle = radians(90-angle)
        step = tan(angle)
        cone = sqrt(sphere) * step
        output = (circle_mask == False) *cone + circle_mask * high
    return output

def test_array_bounds(array_to_test,x,y):
    y_size,x_size = array_to_test.shape
    #print "TEST",x_size,y_size,(x >= 0),(x < x_size),(y >= 0),(y < y_size)
    return (x >= 0) and (x < x_size) and (y >= 0) and (y < y_size)

def test_dot(array_to_test,x,y):
    if not test_array_bounds(array_to_test,x,y):
        return None
    return array_to_test[y,x]

def find_nearby_dot(dotmap,x,y):
    height,width = dotmap.shape
    m = test_dot(dotmap,x,y)
    if m:
        return x,y
    else:
        for r in range(1,max(height,width)):
            for offset in range(0,r+1):
                for test in [[x-offset,y-r],
                    [x-offset,y+r],
                    [x+offset,y-r],
                    [x+offset,y+r],
                    [x+r,y+offset],
                    [x-r,y+offset],
                    [x+r,y-offset],
                    [x-r,y-offset]]:
                    m = test_dot(dotmap,test[0],test[1])
                    if m:
                        return test
        r += 1
    return None

def seek_dot_on_z(dotmap,p1,p2,this_depth):
    x1,y1 = p1
    x2,y2 = p2
    y1_horizontal_move = True
    y2_horizontal_move = True
    x1_vertical_move = True
    x2_vertical_move = True
    #print "Testing %s to %s" % (p1,p2)
    if not test_dot(dotmap,x2,y2):
        #print "failed x2,y2"
        return None
    if x1 < x2:
        xstep = 1
    else:
        xstep = -1
    if y1 < y2:
        ystep = 1
    else:
        ystep = -1
    for x in range(x1,x2,xstep):
        y1_horizontal_move = y1_horizontal_move and test_dot(dotmap,x,y1)
        y2_horizontal_move = y2_horizontal_move and test_dot(dotmap,x,y2)
    for y in range(y1,y2,ystep):
        x1_vertical_move = x1_vertical_move and test_dot(dotmap,x1,y)
        x2_vertical_move = x2_vertical_move and test_dot(dotmap,x2,y)
    positions = []
    #print x1_vertical_move,x2_vertical_move,y1_horizontal_move,y2_horizontal_move
    if x1_vertical_move and y2_horizontal_move:
        positions.append([ "line",[x1,y1,this_depth],[x1,y2,this_depth] ])
        positions.append([ "line",[x1,y2,this_depth],[x2,y2,this_depth] ])
    elif x2_vertical_move and y1_horizontal_move:
        positions.append([ "line",[x1,y1,this_depth],[x2,y1,this_depth] ])
        positions.append([ "line",[x2,y1,this_depth],[x2,y2,this_depth] ])
    #print positions
    travel = abs(x1-x2) + abs(y1-y2)
    return positions

def get_direction_results(dotmap,x,y):
    stress = 0
    results = {}
    for direction in directions:
        x_delta,y_delta = directions[direction]
        next_x = x + x_delta
        next_y = y + y_delta
        result = results[direction] = test_dot(dotmap,next_x,next_y)
        if result:
            stress += 1
    results["overall"] = stress != 0
    results["stress"] = stress
    return results

def next_edge(dotmap, x, y, seek=True, clockwise=True):
    #assumes the directions in the "directions" variable is set correctly for the map
    #if that assumption is wrong, it may go the wrong way around
    positions = [[x,y]]
    go = None
    results = get_direction_results(dotmap,x,y)
    if clockwise:
        test_directions = ["down","left","up","right"]
    else:
        test_directions = ["down","right","up","left"]
    dir_a,dir_b,dir_c,dir_d = test_directions
    if not results[dir_a] and results[dir_b]:
        go = dir_b
    elif not results[dir_b] and results[dir_c]:
        go = dir_c
    elif not results[dir_c] and results[dir_d]:
        go = dir_d
    elif not results[dir_d] and results[dir_a]:
        go = dir_a
    elif seek:
        for direction in test_directions:
            if results[direction]:
                x_delta,y_delta = directions[direction]
                return x+x_delta, y+y_delta, results["stress"]
    if not go:
        return None
    x_delta,y_delta = directions[go]
    return x+x_delta, y+ y_delta, results["stress"]

def trace_layer(dotmap,x,y):
    positions = []
    if test_array_bounds(dotmap,x,y) and dotmap[y,x]:
        positions.append([x,y])
        dotmap[y,x] = False
    position = next_edge(dotmap,x,y)
    while position:
        if position:
            x,y,stress = position
            dotmap[y,x] = False
        positions.append(position)
        position = next_edge(dotmap,x,y)
    return x,y,positions

def zigzag_layer(layer,xin,yin,this_depth):
    x = xin
    y = yin
    positions = []
    #positions.append("#starting at %s,%s" % (x,y))
    pending_positions = []
    direction = last_dir = "left"
    last_directions = ["down","right","up","left"]
    measure = get_direction_results(layer,x,y)
    shift = False
    stress = measure["stress"]
    #print "A",measure
    save_points = [[x,y,this_depth]]
    while measure["overall"]:
        last_stress = stress
        stress = measure["stress"]
        #print "B",measure
        if measure["center"]:
            layer[y,x] = False
            if last_dir != direction or stress != last_stress:
                if len(pending_positions) == 1:
                    positions.append( ["dot",pending_positions[0]] )
                    #print "DOT"
                else:
                    positions.append([ "line_with_stress", pending_positions[0], pending_positions[-1], last_stress ])
                #print [ "line", pending_positions[0], pending_positions[-1] ]
                pending_positions = []
            save_points = [[x,y,this_depth]] + save_points[:10]
            pending_positions.append([x,y,this_depth])
            #print "APPEND",[x,y,this_depth], measure["stress"]
        last_dir = direction
        if shift:
            alt = last_directions.pop(-3)
            last_directions.append(alt)
            shift = False
        elif measure[last_directions[-1]]:
            #keep going that direction
            pass
        elif measure[last_directions[-2]]:
            alt = last_directions.pop(-2)
            last_directions.append(alt)
            shift = True
        #we don't check for -3 when not in shift mode because that would mean it was L/R when we are going R/L
        elif measure[last_directions[-4]]:
            alt = last_directions.pop(-4)
            last_directions.append(alt)
        direction = last_directions[-1]
        x += directions[direction][0]
        y += directions[direction][1]
        measure = get_direction_results(layer,x,y)
        if not measure["overall"]:
            #print "BACKTRACING!"
            backtrack = []
            for dot in save_points:
                testx,testy,testz = dot #testz is not used
                measure = get_direction_results(layer,testx,testy)
                backtrack.append(dot)
                if measure["overall"]:
                    #print "BACKED UP to %s" % dot
                    positions.append([ "line_with_stress", pending_positions[0], pending_positions[-1], last_stress ])
                    #positions.append("#BACK UP to %s" % dot)
                    for bt in backtrack:
                        positions.append(["stress_dot",bt,0]) #no stress because we are just retracing our steps
                    pending_positions = [dot]
                    x,y = testx,testy
                    alt = last_directions.pop(-2)
                    last_directions.append(alt)
                    x += directions[direction][0]
                    y += directions[direction][1]
                    shift = True
                    break
    if pending_positions:
        #positions.append("#add pending positions")
        positions.append([ "line_with_stress", pending_positions[0], pending_positions[-1], last_stress ])
        #positions = positions + pending_positions
        x,y,z = pending_positions[-1] #discard the z
        #positions.append("#line %s to %s" % (pending_positions[0],pending_positions[-1]))
    #positions.append("#ending at %s,%s" % (x,y))
    return x,y,positions

def downsample_to_bit_diameter(image, scale, bit_diameter, bit="square"):
    #print image.shape
    bit_diameter = int(bit_diameter)
    height,width = image.shape
    scaled_width = width*scale
    scaled_height = height*scale
    output = zeros((scaled_height,scaled_width),dtype=integer)
    #coordinates are height,width
    print "output is %s" % str(output.shape)
    print "target width, target height, scale = ",scaled_width,scaled_height,scale
    #print "downsample_to_bit_diamter width=%i height=%i" % (width,height)
    #print "downsample_to_bit_diameter shape:", output.shape
    #print len(image[::bit_diameter,::bit-_diameter].tolist()[0])
    #print "bit_diameter:",bit_diameter
    for y in range(int(scaled_height)):
        for x in range(int(scaled_width)):
            #print "%s:%s,%s:%s = %s" % ( (y)/scale,(y+bit_diameter)/scale,x/scale,(x+bit_diameter)/scale,amax(image[(y)/scale:(y+bit_diameter)/scale,x/scale:(x+bit_diameter)/scale]))
            left = (x-bit_diameter/2)/scale
            right = (x+bit_diameter/2+1)/scale
            top = (y-bit_diameter/2)/scale
            bottom = (y+bit_diameter/2+1)/scale
            if bit == "square":
                left = max( left,  0)
                right = min( right,  width)
                top = max( top, 0)
                bottom = min( bottom, height)
                #this line will have to be a bit more precise for final cuts
                output[y,x] = amax(image[top:bottom,left:right])
            else:
                #print "-"*80
                #print left,right,top,bottom, "at %s,%s" % (y,x)
                my,mx = mgrid[ top:bottom, left:right ]
                mask_for_bit_check = ma.make_mask( (mx>=0) * (mx<width) * (my>=0) * (my<height) )
                left = max( left,  0)
                right = min( right,  width)
                top = max( top, 0)
                bottom = min( bottom, height)
                surface_subset = image[top:bottom,left:right]
                #print "surface:",surface_subset
                surface_subset = surface_subset.flatten()
                bit_subset = extract(mask_for_bit_check,bit)
                #print "surface:",surface_subset.tolist()
                #print "bit:",bit_subset.tolist()
                #print dir(bit_subset)
                #print "image:",surface_subset.shape,"vs","bit:",bit_subset.shape
                try:
                    output[y,x] = amax( surface_subset - bit_subset )
                except:
                    print mask_for_bit_check.sum()
                    raise
                #print "result:",output[y,x]
            #if I save that range instead of doing amax on it, I could:
            #   1. do amax on it for zigzag or trace cuts
            #   or
            #   2. subtract a grid of values from it where 0 is the tip of the bit and then amax the result
            #how do I get a grid that represents the shape of the bit?
            #will that affect the speed too much?
    #print "downsample_to_bit_diameter shape:", output.shape
    return output

def make_top(bottom):
    return zeros(bottom.shape,dtype=integer)

def cut_to_gcode(cuts,x=0,y=0,z=0, cut_speed=500, z_cut_speed=300, z_rapid_speed=400, rapid_speed=700, safe_distance=2,unit="mm",offsets=[0,0,0],minimum_stress=1,dedupe=False):
    #if the next cut location is more than one space away, go to safe_distance before moving
    #if the next cut location is diagonal, go to safe_distance before moving
    #if the next cut depth is not as deep as the current depth, change to the new depth before moving
    #after moving to the next cut location, make sure we are at the right depth
    #if the next cut is a string, it might be "seek" which will tell us we might need to switch to safe_distance before moving

    calculated_cut_speeds = []
    for stress in range(6):
        calculated_speed = ( stress*cut_speed + (5-stress)*rapid_speed )/ 5
        calculated_cut_speeds.append(calculated_speed)
        
    print "calculated cut speeds by stress:",calculated_cut_speeds
    gcode = []
    if unit.lower() == "mm":
        gcode.append("G21")
    elif unit.lower() == "inch":
        gcode.append("G20")
    gcode.append("G17 G90 G64 M3 S3000 M7")
    gcode.append("G0 X0 Y0 F%f" % rapid_speed)
    gcode.append("G0 Z0 F%f" % z_rapid_speed)
    gcode.append("G1 X0 Y0 F%f" % cut_speed)
    gcode.append("G1 Z0 F%f" % z_cut_speed)
    gcode.append("(start object)")
    for cut in cuts:
        if type(cut) == str:
            command = "#"
        elif type(cut[0]) == str:
            command = cut[0]
        else:
            command = "dot"
            cut = ["dot",cut]
        calculated_speed = cut_speed #default to the slow cuts
        #print "CUT[0]:",cut[0]
        if cut == "seek":
            #gcode.append("#seek")
            continue
        elif command == "#" and ( cut.startswith("#") or cut.startswith("(") ):
            gcode.append("(%s)" % cut)
            continue
        elif command in ["line","line_with_stress"]: #start cut from point A and end it later in the loop
            start = cut[1]
            end = cut[2]
            if len(end) < 3 or len(start) < 3:
                print "BAD LINE:",start,end
            if end[2] <> start[2]:
                print "Z mismatch on %s!" % cut

            travel = abs(start[0]-x) + abs(start[1]-y)
            if command == "line_with_stress":
                stress = min( cut[3] + minimum_stress, 5 )
                calculated_speed = calculated_cut_speeds[stress]
            else:
                calculated_speed = cut_speed
            #gcode.append("#start line")
            if travel > 1:
                gcode.append("G0 F%i Z%.3f" % (z_rapid_speed,safe_distance))
                gcode.append("G0 F%i X%.3f Y%.3f" % (rapid_speed,offsets[0]+start[0],offsets[1]+start[1]))
                gcode.append("G1 F%i Z%.3f" % (z_cut_speed,offsets[2]-start[2]))
                z = start[2]
            elif z > start[2]: #we must go up
                #print z,offsets[2]-cut[2]
                gcode.append("G0 F%i Z%.3f" % (z_rapid_speed,offsets[2]-start[2]))
                gcode.append("G1 F%i X%.3f Y%.3f" % (calculated_speed,offsets[0]+start[0],offsets[1]+start[1]))
                z = start[2]
            else:
                gcode.append("G1 F%i X%.3f Y%.3f" % (calculated_speed,offsets[0]+start[0],offsets[1]+start[1]))
                z = start[2]
            gcode.append("G1 F%i X%.3f Y%.3f" % (calculated_speed,offsets[0]+end[0],offsets[1]+end[1]))
            if end[2] != z:
                gcode.append("G1 F%i Z%.3f" % (z_cut_speed,offsets[2]-end[2]))
            x,y,z = end
        elif command == "stress_segment": #cut from the last point to this point
            end = cut[1]
            if end[2] <> z:
                print "Z mismatch on %s!" % cut
            stress = min( cut[2] + minimum_stress, 5 )
            calculated_speed = calculated_cut_speeds[stress]
            #gcode.append("#start line")
            gcode.append("G1 F%i X%.3f Y%.3f" % (calculated_speed, offsets[0]+end[0], offsets[1]+end[1]))
            if end[2] != z:
                gcode.append("G1 F%i Z%.3f" % (z_cut_speed,offsets[2]-end[2]))
            x,y,z = end
        elif command in ["dot","stress_dot"]:
            if command == "stress_dot":
                stress = min( cut[2] + minimum_stress, 5 )
                calculated_speed = calculated_cut_speeds[stress]
            else:
                calculated_speed = cut_speed
            start = cut[1]
            travel = abs(start[0]-x) + abs(start[1]-y)
            if travel > 1:
                gcode.append("G0 F%i Z%.3f" % (z_rapid_speed,safe_distance))
                gcode.append("G0 F%i X%.3f Y%.3f" % (rapid_speed,offsets[0]+start[0],offsets[1]+start[1]))
                z = safe_distance
            elif z > start[2]: #we must go up
                #print z,offsets[2]-cut[2]
                gcode.append("G0 F%i Z%.3f" % (z_rapid_speed,offsets[2]-start[2]))
                gcode.append("G1 F%i X%.3f Y%.3f" % (calculated_speed,offsets[0]+start[0],offsets[1]+start[1]))
                z = start[2]
            else:
                gcode.append("G1 F%i X%.3f Y%.3f" % (calculated_speed,offsets[0]+start[0],offsets[1]+start[1]))
                z = start[2]
            if z != start[2]:
                gcode.append("G1 F%i Z%.3f" % (z_cut_speed,offsets[2]-start[2]))
            x,y,z = start
        elif command == "simple":
            offset_x,offset_y,offset_z = offsets
            x,y,z = cut[1]
            gcode.append("G1 F%i X%.3f Y%.3f Z%.3f" % (cut_speed,offset_x+x,offset_y+y,offset_z-z))
        else:
            print "UNHANDLED COMMAND: %s" % command
            gcode.append("UNHANDLED COMMAND: %s" % command)
        #gcode.append("(done with this command)")
    if not dedupe:
        return gcode
    deduped_gcode = []
    last_line = ""
    for line in gcode:
        if line != last_line:
            deduped_gcode.append(line)
        last_line = line
    return deduped_gcode

def alter_gcode(gcode,adjustments,tidy="Z"):
    #put whatever letters in tidy...FGXYZ
    tidy = tidy.upper()
    altered_gcode = []
    translate = False
    f = g = x = y = z = 0
    ax = ay = az = 0 #altered
    lg = lf = 0 #last G and F
    lax = lay = laz = 0 #last altered
    for line in gcode:
        if line.strip().lower() == "(start object)":
            translate = True
            altered_gcode.append(line)
        elif not translate:
            altered_gcode.append(line)
        elif line.strip().startswith("("):
            altered_gcode.append(line)
        else:
            parts = line.split(" ")
            for part in parts:
                part = part.upper()
                if part.startswith("X"):
                    x = float(part[1:])
                elif part.startswith("Y"):
                    y = float(part[1:])
                elif part.startswith("Z"):
                    z = float(part[1:])
                elif part.startswith("G"):
                    g = int(part[1:])
                elif part.startswith("F"):
                    f = int(part[1:])
            ax,ay,az = x,y,z
            for adjustment in adjustments:
                command,parameter = adjustment
                command = command.lower()
                if command == "rotate":
                    degrees = parameter[0]
                    ax,ay = cos(degrees)*ax - sin(degrees)*ay, sin(degrees)*ay + cos(degrees)*ax
                elif command == "translate":
                    dx,dy,dz = parameter #set our deltas
                    ax += dx
                    ay += dy
                    az += dz
                elif command == "scale":
                    sx,sy,sz = parameter #set our scales
                    ax *= sx
                    ay *= sy
                    az *= sz
            altered_line = []
            ax = "%.02f" % ax
            ay = "%.02f" % ay
            az = "%.02f" % az
            if "G" not in tidy or g != lg:
                altered_line.append("G%i" % g)
            if "F" not in tidy or f != lf:
                altered_line.append("F%i" % f)
            if "X" not in tidy or ax != lax:
                altered_line.append("X%s" % ax)
            if "Y" not in tidy or ay != lay:
                altered_line.append("Y%s" % ay)
            if "Z" not in tidy or az != laz:
                altered_line.append("Z%s" % az)
            lg,lf,lax,lay,laz = g,f,ax,ay,az
            altered_line = " ".join(altered_line)
            if altered_line.strip():
                altered_gcode.append(altered_line)
    return altered_gcode

def zigzag(bottom):
    top = make_top(bottom)
    cut_positions = []
    layer = bottom > top
    start_position = find_nearby_dot(layer,0,0)
    depth = 1
    layer = bottom > top
    while start_position:
        #cut_positions = cut_positions + ["#seek"]
        x,y = start_position
        #print start_position
        #print "%i to go" % (layer == False).sum()
        x,y,positions = zigzag_layer(layer,x,y,depth)
        cut_positions = cut_positions + positions
        if (layer == False).all():
            print depth,"of",bottom.max()
            top = top.clip(depth,bottom)
            depth += 1
            layer = bottom > top
            start_position = find_nearby_dot(layer,x,y)
        else:
            start_position = find_nearby_dot(layer,x,y)
            if True: #I want to be able to turn this on and off for testing
                seek = seek_dot_on_z( bottom > depth, (x,y), start_position, depth)
                if seek:
                    #print "SEEK ON Z!"
                    cut_positions = cut_positions + seek
                #else:
                    #print "FAIL SEEK IN Z!"
    return cut_positions

def trace(bottom):
    top = make_top(bottom)
    cut_positions = []
    layer = bottom > top
    start_position = find_nearby_dot(layer,0,0)
    depth = 1
    layer = bottom > top
    while start_position:
        cut_positions = cut_positions + ["seek"]
        x,y = start_position
        #print start_position
        x,y,positions = trace_layer(layer,x,y)
        for position in positions:
            if len(position) == 3:
                cx,cy,stress = position
                cut_positions.append(["stress_dot",[cx,cy,depth],stress])
            else:
                cx,cy = position
                cut_positions.append(["dot",[cx,cy,depth]])
        if (layer == False).all():
            print depth,"of",bottom.max()
            top = top.clip(depth,bottom)
            depth += 1
            layer = bottom > top
            start_position = find_nearby_dot(layer,x,y)
        else:
            start_position = find_nearby_dot(layer,x,y)
            if True: #I want to be able to turn this on and off for testing
                seek = seek_dot_on_z( bottom > depth, (x,y), start_position, depth)
                if seek:
                    #print "SEEK ON Z!"
                    cut_positions = cut_positions + seek
                #else:
                    #print "FAIL SEEK IN Z!"
    return cut_positions

def get_outline(bottom,depth):
    base = bottom == depth
    above = bottom >= depth
    #find out if there are dots in either of the 4 horizontal locations at the given depth
    u = roll(base,1,0) 
    d = roll(base,-1,0)
    l = roll(base,1,1)
    r = roll(base,-1,1)
    #the wrap makes false positives
    u[0,:] = False
    d[-1,:] = False
    l[:,0] = False
    r[:,-1] = False
    #boolean + boolean means OR
    #boolean * boolean means AND
    layer = ((u*r)+(d*r)+(u*l)+(d*l)+base) * above
    return layer
  
def final(bottom,passes="xy"):
    passes = passes.lower()
    cut_positions = []
    height,width = bottom.shape
    xrange = range(width)
    if "x" in passes:
        last_y = last_x = last_z = 0
        we_skipped_the_last_dot = False
        for y in range(height):
            for x in xrange:
                z = bottom[y,x]
                if z != last_z:
                    if we_skipped_the_last_dot:
                        cut_positions.append(("simple",(last_x,y,last_z)))
                    we_skipped_the_last_dot = False
                    cut_positions.append(("simple",(x,y,z)))
                else:
                    we_skipped_the_last_dot = True
                last_x,last_y,last_z = x,y,z
            xrange.reverse()
        if we_skipped_the_last_dot:
            cut_positions.append(("simple",(last_x,y,last_z)))
        cut_positions.append(("dot",(last_x,y,last_z)))
    we_skipped_the_last_dot = False
    last_y = last_x = last_z = 0
    if "y" in passes:
        we_skipped_the_last_dot = False
        yrange = range(height)
        yrange.reverse()
        cut_positions.append(("dot",(0,0,0)))
        for x in xrange:
            for y in yrange:
                z = bottom[y,x]
                if z != last_z:
                    if we_skipped_the_last_dot:
                        cut_positions.append(("simple",(x,last_y,last_z)))
                    we_skipped_the_last_dot = False
                    cut_positions.append(("simple",(x,y,z)))
                else:
                    we_skipped_the_last_dot = True
                last_x,last_y,last_z = x,y,z
            yrange.reverse()
        if we_skipped_the_last_dot:
            cut_positions.append(("simple",(x,last_y,last_z)))
        cut_positions.append(("simple",(last_x,y,last_z)))
    return cut_positions

if False: #turn this to True to do a simple test for fitting the shape of the bit to the part
    blah = array([[100,100,100,100,100],[100,100,100,100,100],[100,50,0,100,100],[100,100,100,100,100],[100,100,100,100,100]])
    bit = array([[1000,1000,1000,1000,1000],[1000,1000,1000,1000,1000],[1000,20,0,50,1000],[1000,1000,1000,1000,1000],[1000,1000,1000,1000,1000]])
    out = downsample_to_bit_diameter(blah,1,5,bit)
    print "OUT:",out
    exit()

def get_parameters(parameters={}):
    if not parameters.has_key("misc"):
        parameters["misc"] = []
    params = argv[1:]
    while params:
        if params[0].startswith("--"):
            p = params.pop(0)[2:]
            if p.count("=") == 1:
                field,value = p.split("=")
                parameters[field]=value
            else:
                parameters[p] = ""
            params
        elif params[0].startswith("-") and len(params) >= 2 and not params[1].startswith("-"):
            p = params.pop(0)[1:]
            f = params.pop(0)
            parameters[p] = f
        elif params[0].startswith("-"):
            print "I was expecting a value after %s, but did not see one." % params[0]
            exit(1)
        else:
            parameters["misc"].append( params.pop(0) )
    return parameters

if __name__ == "__main__":
    try:
        parameters = get_parameters(parameters={"bit":"square","tidy":"GFXYZ","final-passes":"xy","stl-detail":"1"})
        input_file = parameters["image"]
        dimension_restricted = parameters["match"]
        dimension_measurement = parameters["size"]
        if input_file.upper().endswith("STL"):
            stl_detail = float(parameters["stl-detail"])
        else:
            thickness = float(parameters["depth"])
        bit_diameter = parameters["bit-diameter"]
        pattern = parameters["method"]
        if parameters.has_key("output"):
            output_filename = parameters["output"]
        else:
            output_filename = input_file.rsplit(".")[0] + ".rough-cut.gcode"
        bit_to_use = parameters["bit"]
        output_file = open(output_filename, "w")
    except:
        print 'USAGE: python bucket_mill.py -image "Best Mom Ever Heart3.gif" --match=width --size=200 --depth=20 --bit-diameter=3 --method=trace --output=test.gcode'
        print '\t--match must be set to "W" or "WIDTH" or "H" or "HEIGHT"'
        print '\t--size is the size of the width or height (whichever you specified in --match)'
        print '\tAll measurements are in millimeters'
        print '\tThe bit can be set by --bit="ball" other options are sphere (same thing), square (default), cylinder, v90 (or some other angle else than 90)'
        print '\t--method sets the milling pattern to use (trace or zigzag or final)'
        print '\tIf you do not define the output file, it will decide one based on the file name.'
        print '\t--final-passes="xy" will set both x cuts and y cuts for the final cut. You can choose x, y or xy.'
        print '\t--tidy="GFXYZ" chooses which gcode commands to reduce duplicates of'
        print '\t--stl-detail sets the amount of dots per mm for imported STL files.'
        exit(1)

    print "input file: %s" % input_file
    print "dimension_restricted: %s" % dimension_restricted
    print "dimension_measurement: %s" % dimension_measurement
    print "bit diameter: %s" % bit_diameter
    print "pattern: %s" % pattern
    print "output file name: %s" % output_filename

    if input_file.upper().endswith("STL"):
        print "STL detail: %f" % stl_detail
        your_mesh = mesh.Mesh.from_file(input_file)
        minx,miny,minz = ( your_mesh.x.min(),your_mesh.y.min(),your_mesh.z.min() )
        your_mesh.x = your_mesh.x - minx
        your_mesh.y = your_mesh.y - miny
        your_mesh.z = your_mesh.z - minz
        print "Z:",your_mesh.z.min(),your_mesh.z.max()
        #your_mesh.z = 1+255.0/your_mesh.z.max() * your_mesh.z
        minx,maxx,miny,maxy = ( your_mesh.x.min(),your_mesh.x.max(),your_mesh.y.min(),your_mesh.y.max() )
        print "X: %0.3f - %0.3f\tY: %0.3f - %0.3f" % (minx,maxx,miny,maxy)
        scale = 1.0
        thickness_precision=1
        if dimension_restricted.upper() in ["W","WIDTH"]:
            scale = float(dimension_measurement)*stl_detail/maxx
        elif dimension_restricted.upper() in ["H","HEIGHT"]:
            scale = float(dimension_measurement)*stl_detail/maxy
        your_mesh.x = your_mesh.x * scale
        your_mesh.y = your_mesh.y * scale
        your_mesh.z = your_mesh.z * scale
        width,height = ( int(your_mesh.x.max()+1), int(your_mesh.y.max()+1) )
        bottom = zeros((width,height))
        for i in range(len(your_mesh.x)):
            x = your_mesh.x[i]
            y = your_mesh.y[i]
            z = your_mesh.z[i]
            bottom[int(x[0]),int(y[0])] = max(bottom[int(x[0]),int(y[0])], int(z[0]))
            bottom[int(x[1]),int(y[1])] = max(bottom[int(x[1]),int(y[1])], int(z[1]))
            bottom[int(x[2]),int(y[2])] = max(bottom[int(x[2]),int(y[2])], int(z[2]))
            if (x.ptp() > 1) or (y.ptp() > 1):
                #the triangle dots are far enough apart, we should try to get 4 more dots and see if that helps
                p1 = [x.mean(),y.mean(),z.mean()]
                p2 = [x[:2].mean(),y[:2].mean(),z[:2].mean()]
                p3 = [x[1:].mean(),y[1:].mean(),z[1:].mean()]
                p4 = [(x[0]+x[2])/2,(y[0]+y[2])/2,(z[0]+z[2])/2]
                for p in [p1,p2,p3,p4]:
                    bottom[int(p[0]),int(p[1])] = max(bottom[int(p[0]),int(p[1])], int(p[2]))
        print "cut image width,height,overall size:",width,height,width*height
        width = width - 1
        height = height - 1
    else:
        print "thickness: %s" % thickness
        cut_image = Image.open(input_file)
        cut_image.convert("L") # Convert image to grayscale
        width, height = cut_image.size
        cut_image = cut_image.transpose(Image.FLIP_TOP_BOTTOM) #The bottom left is 0,0 in the CNC, but the upper left is 0,0 in the image
        print len(cut_image.getdata())
        print "cut image width,height,overall size:",width,height,width*height
        bottom = array(cut_image)
    scale = 1.0
    thickness_precision=1
    if dimension_restricted.upper() in ["W","WIDTH"]:
        scale = float(dimension_measurement)/width
    elif dimension_restricted.upper() in ["H","HEIGHT"]:
        scale = float(dimension_measurement)/height
    scale_to_use = scale
    safety = 1
    print "SCALE: %0.03f" % scale
    if scale < 1.0:
        print "A scale of less than 1 causes bit matching to fail."
        print "This is why bit matching for STL files fails."
    if pattern.upper() == "FINAL":
        thickness_precision=10 #get 1/10 of a mm precision
        scale_to_use = 1.0
        safety = 0
        if bit_to_use.upper() == "SQUARE":
            bottom = downsample_to_bit_diameter(bottom,scale_to_use,float(bit_diameter)/scale)
        else:
            which_bit = bit_pixels(bit_shape=bit_to_use,diameter=float(bit_diameter)/scale)
            bottom = downsample_to_bit_diameter(bottom,scale_to_use,float(bit_diameter)/scale,bit=which_bit)
    else:
        if bit_to_use.upper() == "SQUARE":
            bottom = downsample_to_bit_diameter(bottom,scale_to_use,float(bit_diameter))
        else:
            which_bit = bit_pixels(bit_shape=bit_to_use,diameter=float(bit_diameter)/scale)
            bottom = downsample_to_bit_diameter(bottom,scale_to_use,float(bit_diameter),bit=which_bit)
    if input_file.upper().endswith("STL"):
        #print which_bit.tolist()
        print "resolution of cut in pixels:",bottom.shape
        print "bottom goes from %i to %i" % (bottom.min(),bottom.max())
        print "get the layer count we want"
        #Z is already scaled
        bottom =  ( bottom.max()-bottom ) - stl_detail
        print "bottom goes from %i to %i" % (bottom.min(),bottom.max())
        thickness_precision = 1/scale
    else:
        print "resolution of cut in pixels:",bottom.shape
        print "bottom goes from %i to %i" % (bottom.min(),bottom.max())
        print "get the layer count we want"
        render_thickness = thickness*thickness_precision
        print "render thickness:",render_thickness
        bottom = int(render_thickness) -safety - bottom * int(render_thickness) / 256
        
    print "bottom goes from %i to %i" % (bottom.min(),bottom.max())
    cut_positions = []

    if pattern.upper() == "ZIGZAG":
        print "ZIGZAG ONE LAYER AT A TIME"
        cut_positions = zigzag(bottom)
        print "We had %i cuts and %i seeks." % (len(cut_positions)-cut_positions.count("seek"), cut_positions.count("seek"))
    elif pattern.upper() == "TRACE":
        print "TRACE AROUND THE EDGES, ONE LAYER AT A TIME"
        cut_positions = trace(bottom)
        print "We had %i cuts and %i seeks." % (len(cut_positions)-cut_positions.count("seek"), cut_positions.count("seek"))
    elif pattern.upper() == "FINAL":
        print "MAKE A FINAL CUT"
        #we should first use a size 10-20 times larger than the mm of the item so we have good detail
        cut_positions = final(bottom,passes=parameters["final-passes"])
        #we should scale gcode down later
        print "We had %i cuts and %i seeks." % (len(cut_positions)-cut_positions.count("seek"), cut_positions.count("seek"))
    print "TEST GCODE GENERATION"
    gcode = cut_to_gcode(cut_positions)
    if pattern.upper() == "FINAL":
        print "scaling by %s,%s,%s" % (scale,scale,1.0/thickness_precision)
        gcode = alter_gcode(gcode,[("scale",(scale,scale,1.0/thickness_precision))],tidy=parameters["tidy"])
    else:
        print "cleaning up the gcode a little more"
        gcode = alter_gcode(gcode,[],parameters["tidy"])
    for line in gcode:
        output_file.write(line+"\r\n")
    output_file.close()