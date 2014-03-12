import libtcodpy as libtcod
import math
import textwrap

#######################
#   SETUP VARIABLES   #
#######################

#Screen generation Variables
SCREEN_WIDTH = 80 
SCREEN_HEIGHT = 50
LIMIT_FPS = 20

#GUI Variables
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
INVENTORY_WIDTH = 50

#Message Variables
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1

#Map Generation Variables
MAP_WIDTH = 80
MAP_HEIGHT = 43

#Room generator Variables
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30
MAX_ROOM_MONSTERS = 3
MAX_ROOM_ITEMS = 2

#ITEM VARIABLES
HEAL_AMOUNT = 4
LIGHTNING_DAMAGE = 20
LIGHTNING_RANGE = 5
CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8

#FOV Variables
FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10


#colors!
color_dark_wall = libtcod.Color(165, 103, 41)
color_dark_ground = libtcod.Color(100, 100, 150)
color_light_wall = libtcod.Color(130, 110, 50)
color_light_ground = libtcod.Color(200, 180, 50)


#################
#   Classes     #
#################

class Object:
    #This is a generic object
    #Always represented by something on screen
    def __init__(self, x, y, char, name, color, blocks = False, fighter = None, ai = None, item = None):
        self.name = name
        self.blocks = blocks
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.fighter = fighter
        self.item = item
        if self.item:
            self.item.owner = self
        if self.fighter:
            self.fighter.owner = self
        self.ai = ai
        if self.ai:
            self.ai.owner = self
    
    def move(self, dx, dy):
        if not is_blocked(self.x + dx, self.y + dy):
            #move by the given amount IF not blocked
            self.x += dx
            self.y += dy
            
    def move_towards(self, target_x, target_y):
        #vector that shit dog
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx ** 2 + dy ** 2)
        
        #normalize, round it and make it an integer
        dx = int(round(dx / distance))
        dy = int(round(dy / distance))
        self.move(dx, dy)
        
        
    def distance_to(self, other):
        #returns distance
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)
    
    def send_to_back(self):
        #make it drawn first so it shows up on bottom
        global objects
        objects.remove(self)
        objects.insert(0, self)
    
    def draw(self):
        #set the color and then draw the character that represents this object at its position
        libtcod.console_set_default_foreground(con, self.color)
        libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)
        
    def clear(self):
        #erase the character that represents this object
        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)

class Tile:
    #a tile of the map
    def __init__(self, blocked, block_sight = None):
        self.blocked = blocked
        self.explored = False
        
        #by default, if a tile is blocked it should block sight
        if block_sight is None: block_sight = blocked
        self.block_sight = block_sight
        
class Rect:
    #a rectangle on the map. used to characterize a room.
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h
 
    def center(self):
        center_x = (self.x1 + self.x2) / 2
        center_y = (self.y1 + self.y2) / 2
        return (center_x, center_y)
 
    def intersect(self, other):
        #returns true if this rectangle intersects with another one
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and
                self.y1 <= other.y2 and self.y2 >= other.y1)

class Fighter:
    #combat shenanigans
    def __init__(self, hp, defense, power, death_function = None):
        self.max_hp = hp
        self.hp = hp
        self.defense = defense
        self.power = power
        self.death_function = death_function
        
    def take_damage(self, damage):
        #damage applied
        if damage > 0:
            self.hp -= damage
        if self.hp <= 0:
            function = self.death_function
            if function is not None:
                function(self.owner)
    
        
    def attack(self, target):
        # attacking damage and what not
        damage = self.power - target.fighter.defense
        
        if damage > 0:
            #make target take damage
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' + str(damage) + ' hit points.')
            target.fighter.take_damage(damage)
        else:
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect!')
    def heal(self, amount):
        #heal by x
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp
        
class BasicMonster:
    #AI!!!
    def take_turn(self):
        monster = self.owner
        if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
            
            #move towards player!
            if monster.distance_to(player) >= 2:
                monster.move_towards(player.x, player.y)
            
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)
                
class ConfusedMonster:
    #AI For stupid people
    def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns
    
    def take_turn(self):
        if self.num_turns > 0:
            #move randomly
            self.owner.move(libtcod.random_get_int(0,-1, 1), libtcod.random_get_int(0, -1, 1))
            self.num_turns -= 1
        
        else:
            self.owner.ai = self.old_ai
            message('The ' + self.owner.name + ' is no longer confused!', libtcod.red)
            

class Item:
    #an item that can be picked up and used.
    def __init__(self, use_function = None):
        self.use_function = use_function
    
    def pick_up(self):
        #add to the player's inventory and remove from the map
        if len(inventory) >= 26:
            message('Your inventory is full, cannot pick up ' + self.owner.name + '.', libtcod.red)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message('You picked up a ' + self.owner.name + '!', libtcod.green)
    def use(self):
        #use it!
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used.')
        else:
            if self.use_function() != 'cancelled':
                inventory.remove(self.owner)

################
#   Functions  #
################

# Map Generation!
def create_h_tunnel(x1, x2, y):
    #creates a horizontal tunnel to join rooms
    global map
    for x in range(min(x1, x2), max(x1, x2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False

def create_v_tunnel(y1, y2, x):
    #Creates a vertical tunnel to join rooms
    global map
    for y in range(min(y1, y2), max(y1, y2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False
        
def make_map():
    global map, player
    
    #Make a map with unblocked tiles
    map = [[ Tile(True)
        for y in range(MAP_HEIGHT) ]
            for x in range(MAP_WIDTH) ]
            
    
    #create RANDOM DUNGEON
    rooms = []
    num_rooms = 0
    
    for r in range(MAX_ROOMS):
        #random width and height
        w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        #random position on map
        x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
        y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)
        
        #Rect class makes rectangeles
        new_room = Rect(x, y, w, h)
        
        #run through rooms to confirm no intersect
        failed = False
        for other_room in rooms:
            if new_room.intersect(other_room):
                failed = True
                break
                
        if not failed:
            #No intersections go
            
            #paint it
            create_room(new_room)
            place_objects(new_room)
            
            #center coords
            (new_x, new_y) = new_room.center()
            
            if num_rooms == 0:
                player.x = new_x
                player.y = new_y
            else:
                #all other rooms
                #connect that shit yo
                
                #center of previous rooms #what?!
                (prev_x, prev_y) = rooms[num_rooms-1].center()
                
                #flip a coin
                if libtcod.random_get_int(0, 0, 1) == 1:
                    #go horizontal, then vert
                    create_h_tunnel(prev_x, new_x, prev_y)
                    create_v_tunnel(prev_y, new_y, new_x)
                else:
                    #go vert then horziontal
                    create_v_tunnel(prev_y, new_y, prev_x)
                    create_h_tunnel(prev_x, new_x, new_y)
                #now add to the list of rooms
            rooms.append(new_room)
            num_rooms += 1
        
def place_objects(room):
    #place random monsters
    num_monsters = libtcod.random_get_int(0,0, MAX_ROOM_MONSTERS)
    
    for i in range(num_monsters):
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)
    
        if not is_blocked(x, y):
            if libtcod.random_get_int(0, 0, 100) < 80:
                #ORCS ARE AT THE GATES
                fighter_component = Fighter(hp = 10, defense = 0, power = 3, death_function = monster_death)
                ai_component = BasicMonster()
                
                monster = Object(x, y, 'o', 'orc', libtcod.desaturated_green, blocks = True, fighter = fighter_component, ai = ai_component)
            else:
                # le sigh, they brought a cave troll
                fighter_component = Fighter(hp = 16, defense = 1, power = 4, death_function = monster_death)
                ai_component = BasicMonster()
                
                monster = Object(x, y, 'T', 'troll', libtcod.darker_green, blocks = True, fighter = fighter_component, ai = ai_component)
        
            objects.append(monster)
    num_items = libtcod.random_get_int(0, 0, MAX_ROOM_ITEMS)
    for i in range(num_items):
        #choose random spot for item
        x = libtcod.random_get_int(0, room.x1+1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)
        
        #only place if not blocked
        if not is_blocked(x, y):
            dice = libtcod.random_get_int(0, 0, 100)
            if dice < 60:
                #create heals
                item_component = Item(use_function = cast_heal)
                item = Object(x, y, '!', 'healing potion', libtcod.violet, item = item_component)
                
                objects.append(item)
                item.send_to_back()
            elif dice < 80:
                #create a lightning bolt scroll
                item_component = Item(use_function = cast_lightning)
                item = Object(x, y, '#', 'Scroll of Lightning Bolt', libtcod.light_red, item = item_component)
                objects.append(item)
                item.send_to_back()
            else:
                #create a confuse scroll
                item_component = Item(use_function = cast_confuse)
                item = Object(x, y, '#', 'Scroll of Confusion', libtcod.light_red, item = item_component)
                objects.append(item)
                item.send_to_back()

                
def create_room(room):
    global map
    #go through the tiles in the rectangle and make them passable
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False
            
            
########### Rendering Functions!

def render_all():
    global color_dark_wall, color_light_wall
    global color_dark_ground, color_light_ground
    global fov_recompute
    
    if fov_recompute:
        fov_recompute = False
        libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)

    #draw all objects in the list
    for object in objects:
        if libtcod.map_is_in_fov(fov_map, object.x, object.y):
            if object != player:
                object.draw()
            player.draw()
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            wall = map[x][y].block_sight
            visible = libtcod.map_is_in_fov(fov_map, x, y)
            if not visible:
                if map[x][y].explored:
                    if wall:
                        libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET)
                    else:
                        libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)
            else:
                if wall:
                    libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET)
                else:
                    libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET)
                map[x][y].explored = True
        
    libtcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)
    
    libtcod.console_set_default_background(panel, libtcod.black)
    libtcod.console_clear(panel)
    
    y = 1
    for (line, color) in game_msgs:
        libtcod.console_set_default_foreground(panel, color)
        libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
        y += 1
    
    #show stats
    render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp, libtcod.light_red, libtcod.darker_red)
    
    #display under mouse
    libtcod.console_set_default_foreground(panel, libtcod.light_gray)
    libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())
        
    libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)

def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
    #render a bar( xp hp shenanigans)
    bar_width = int(float(value) / maximum * total_width)
    
    #background stuff
    libtcod.console_set_default_background(panel, back_color)
    libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)
    
    #bar time!
    libtcod.console_set_default_background(panel, bar_color)
    if bar_width > 0:
        libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)
    
    #text and stuff
    libtcod.console_set_default_foreground(panel, libtcod.white)
    libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER, name + ': ' + str(value) + '/' + str(maximum))


def message(new_msg, color = libtcod.white):
    #split message if too long
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)
    
    for line in new_msg_lines:
        #if buffer is full, remove first line to make room
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]
        
        #add line as tuple
        game_msgs.append( (line, color) )

def get_names_under_mouse():
    global mouse
    
    #return a string with name of objects under mouse
    (x, y) = (mouse.cx, mouse.cy)
    
    #create a list of all objects in view and under mouse
    names = [obj.name for obj in objects if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
    
    names = ', '.join(names)
    return names.capitalize()

def menu(header, options, width):
    if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options!')
    
    #calculate height and what not
    header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
    height = len(options) + header_height
    #create off screen console shenanigans
    window = libtcod.console_new(width, height)
    
    #print header and auto-wrap
    libtcod.console_set_default_foreground(window, libtcod.white)
    libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)
    
    #print all options
    y = header_height
    letter_index = ord('a')
    for option_text in options:
        text = '(' + chr(letter_index) + ') ' + option_text
        libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
        y += 1
        letter_index += 1
    
    #blit contents
    x = SCREEN_WIDTH / 2 - width / 2
    y = SCREEN_HEIGHT / 2 - height / 2
    libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)
    
    libtcod.console_flush()
    key = libtcod.console_wait_for_keypress(True)
    
    index = key.c - ord('a')
    if index >= 0 and index < len(options): return index
    return None

def inventory_menu(header):
    #show menu
    if len(inventory) == 0:
        options = ['Inventory is empty']
    else:
        options = [item.name for item in inventory]
    
    index = menu(header, options, INVENTORY_WIDTH)
    if index is None or len(inventory) == 0: return None
    return inventory[index].item
     
############## Game Operations!


def handle_keys():
    global fov_recompute, game_state
    global key
    
    
    #movement keys
    if game_state == 'playing':
        if key.vk == libtcod.KEY_UP:
            player_move_or_attack(0, -1)

        elif key.vk == libtcod.KEY_DOWN:
            player_move_or_attack(0, 1)
        
        elif key.vk == libtcod.KEY_LEFT:
            player_move_or_attack(-1, 0)
        
        elif key.vk == libtcod.KEY_RIGHT:
            player_move_or_attack(1, 0)
        else:
            key_char = chr(key.c)
            
            if key_char == 'g':
                #pick up an item
                for object in objects:
                    if object.x == player.x and object.y == player.y and object.item:
                        object.item.pick_up()
                        break
            if key_char == 'i':
                #show inventory, use items...
                chosen_item = inventory_menu('Press the key next to an item to use it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.use()
                    
            return 'didnt-take-turn'
        

    if key.vk == libtcod.KEY_ENTER and key.lalt:
        #Alt + Enter: toggle fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
    
    elif key.vk == libtcod.KEY_ESCAPE:
        return 'exit' #exit game

                

def is_blocked(x, y):
    #test tile
    if map[x][y].blocked:
        return True
    
    for object in objects:
        if object.blocks and object.x == x and object.y == y:
            return True
    
    return False

def player_move_or_attack(dx, dy):
    global fov_recompute
    
    x = player.x + dx
    y = player.y + dy
    
    target = None
    for object in objects:
        if object.x == x and object.y == y and object.fighter:
            target = object
            break
    if target is not None:
        player.fighter.attack(target)
    else:
        player.move(dx, dy)
        fov_recompute = True

def player_death(player):
    global game_state
    message('You died!')
    game_state = 'dead'
    
    player.char = '%'
    player.color = libtcod.dark_red
    
def monster_death(monster):
    message(monster.name.capitalize() + ' is dead!')
    monster.char = '%'
    monster.color = libtcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of ' + monster.name
    monster.send_to_back()
    
def closest_monster(max_range):
    closest_enemy = None
    closest_dist = max_range + 1
    
    for object in objects:
        if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
            #calc distance
            dist = player.distance_to(object)
            if dist < closest_dist:
                closest_enemy = object
                closest_dist = dist
    return closest_enemy
    
########    Spells!
 
def cast_heal():
    #heal that boy
    if player.fighter.hp == player.fighter.max_hp:
        message('You are already at full health.', libtcod.red)
        return 'cancelled'
    message('You feel slightly better!', libtcod.light_violet)
    player.fighter.heal(HEAL_AMOUNT)

def cast_lightning():
    #find closest enemy and shock!
    monster = closest_monster(LIGHTNING_RANGE)
    if monster is None:
        message('No enemy is close enough to strike.', libtcod.red)
        return 'cancelled'
        
    message('A lightning bolt strikes the ' + monster.name + ' with a loud thunder! The damage is ' + str(LIGHTNING_DAMAGE) + ' hit points.', libtcod.light_blue)
    monster.fighter.take_damage(LIGHTNING_DAMAGE)

def cast_confuse():
    #find closest enemy and shock!
    monster = closest_monster(CONFUSE_RANGE)
    if monster is None:
        message('No enemy is close enough to confuse.', libtcod.red)
        return 'cancelled'
        
    old_ai = monster.ai
    monster.ai = ConfusedMonster(old_ai)
    monster.ai.owner = monster
    message('The eyes of the ' + monster.name + ' look vacant, as he starts to stumble around!', libtcod.light_green)
        
    
#############################
#   Pre-Loop Declaration    #
#############################


libtcod.console_set_custom_font('arial10x10.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD) #SET FONT

libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'python/libtcod tutorial', False) #INITIALIZE
con = libtcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)

libtcod.sys_set_fps(LIMIT_FPS) #SET FPS
    
fighter_component = Fighter(hp = 30, defense = 2, power = 5, death_function = player_death)    
player = Object(0, 0, 'W', 'player', libtcod.white, blocks = True, fighter = fighter_component)
objects = [player]
make_map()  
game_msgs = [] 
inventory = []

fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
for y in range(MAP_HEIGHT):
    for x in range(MAP_WIDTH):
        libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)
        
        
fov_recompute = True
game_state = 'playing'
player_action = None

#setup for GUI
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)
message('Welcome stranger! Prepare to face danger and doom!', libtcod.red)
    
mouse = libtcod.Mouse()
key = libtcod.Key()


#########################
#       MAIN LOOP       #
#########################
    
while not libtcod.console_is_window_closed():
    libtcod.console_set_default_foreground(con, libtcod.white)
    libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)
    
    render_all()
    
    libtcod.console_flush()
    for object in objects:
        object.clear()
    #handle keys and exit game if necessary
    player_action = handle_keys()
    
    if game_state == 'playing' and player_action != 'didnt-take-turn':
        for object in objects:
            if object.ai:
                object.ai.take_turn()
                
    
    if player_action == 'exit':
        break
