import libtcodpy as libtcod
import math
import textwrap
import shelve

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
CHARACTER_SCREEN_WIDTH = 30

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


#ITEM VARIABLES
HEAL_AMOUNT = 40
LIGHTNING_DAMAGE = 40
LIGHTNING_RANGE = 5
CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8
FIREBALL_RADIUS = 3
FIREBALL_DAMAGE = 25

#FOV Variables
FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10

#colors!
color_dark_wall = libtcod.Color(165, 103, 41)
color_dark_ground = libtcod.Color(100, 100, 150)
color_light_wall = libtcod.Color(130, 110, 50)
color_light_ground = libtcod.Color(200, 180, 50)

#Experience and whut not
LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150
LEVEL_SCREEN_WIDTH = 40
PLAYER_SKILL_DAMAGE = 2
BUFF_AMOUNT = 2

#################
#   Classes     #
#################

class Object:
    #This is a generic object
    #Always represented by something on screen
    def __init__(self, x, y, char, name, color, blocks = False, fighter = None, ai = None, item = None, always_visible = False, equipment = None):
        self.name = name
        self.blocks = blocks
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.fighter = fighter
        self.item = item
        self.always_visible = always_visible
        if self.item:
            self.item.owner = self
        if self.fighter:
            self.fighter.owner = self
        self.ai = ai
        if self.ai:
            self.ai.owner = self
        self.equipment = equipment
        if self.equipment:
            self.equipment.owner = self
            self.item = Item()
            self.item.owner = self
    
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
        if (libtcod.map_is_in_fov(fov_map, self.x, self.y) or
            (self.always_visible and map[self.x][self.y].explored)):      
            libtcod.console_set_default_foreground(con, self.color)
            libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)
        
        
    def clear(self):
        #erase the character that represents this object
        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)
    
    def distance(self, x, y):
        #return distance to some coords
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

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
    def __init__(self, hp, defense, power, xp, death_function = None):
        self.base_max_hp = hp
        self.hp = hp
        self.base_defense = defense
        self.base_power = power
        self.xp = xp
        self.death_function = death_function
    @property
    def power(self):
        bonus = sum(equipment.power_bonus for equipment in get_all_equipped(self.owner))
        return self.base_power + bonus
    
    @property
    def defense(self):
        bonus = sum(equipment.defense_bonus for equipment in get_all_equipped(self.owner))
        return self.base_defense + bonus    
    
    @property
    def max_hp(self):
        bonus = sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
        return self.base_max_hp + bonus
    
    def take_damage(self, damage):
        #damage applied
        if damage > 0:
            self.hp -= damage
        if self.hp <= 0:
            function = self.death_function
            if function is not None:
                function(self.owner)
            if self.owner != player:
                player.fighter.xp += self.xp
    
        
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
            #special cases... equipment with free slots.
            equipment = self.owner.equipment
            if equipment and get_equipped_in_slot(equipment.slot) is None:
                equipment.equip()
            
    def use(self):
        #use it!
        if self.owner.equipment:
            self.owner.equipment.toggle_equip()
            return
        
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used.')
        else:
            if self.use_function() != 'cancelled':
                inventory.remove(self.owner) 

    def drop(self):
        objects.append(self.owner)
        inventory.remove(self.owner)
        self.owner.x = player.x
        self.owner.y = player.y
        if self.owner.equipment:
            self.owner.equipment.dequip()
        message('You dropped a ' + self.owner.name + '.', libtcod.yellow)

class Equipment:
    #objects that can be equipped
    def __init__(self, slot, power_bonus = 0, defense_bonus = 0, max_hp_bonus = 0):
        self.slot = slot
        self.is_equipped = False
        self.power_bonus = power_bonus
        self.defense_bonus = defense_bonus
        self.max_hp_bonus = max_hp_bonus
        
    def toggle_equip(self):
        if self.is_equipped:
            self.dequip()
        else:
            self.equip()
    def equip(self):
        #equip object and show a message about it
        old_equipment = get_equipped_in_slot(self.slot)
        if old_equipment is not None:
            old_equipment.dequip()
        
        self.is_equipped = True
        message('Equipped ' + self.owner.name + ' on ' + self.slot + '.', libtcod.light_green)
        
    def dequip(self):
        #remove objects and what not
        if not self.is_equipped: return
        self.is_equipped = False
        message('Dequipped ' + self.owner.name + ' from ' + self.slot + '.', libtcod.light_yellow)
        
class Skill:
    def __init__(self, name, use_function = None):
        self.name = name
        self.use_function = use_function
    
    def use(self):
        if self.use_function == None:
            message('The skill ' + self.owner.name + ' cannot be used', libtcod.yellow)
        self.use_function()    
            
        
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
    global map, objects, stairs
    
    objects = [player]
    
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
    #create stairs at the center of the last room
    stairs = Object(new_x, new_y, '<', 'stairs', libtcod.white, always_visible = True)
    objects.append(stairs)
    stairs.send_to_back()
        
def place_objects(room):
    #place random monsters
    #max monsters per room
    max_monsters = from_dungeon_level([[2, 1], [3, 4], [5, 6]])
    
    #chance for monster
    monster_chances = {}
    monster_chances['orc'] = from_dungeon_level([[80, 1], [10, 5], [0, 9]])
    monster_chances['orc2'] = from_dungeon_level([[20, 4], [70, 5], [80, 7]])
    monster_chances['troll'] = from_dungeon_level([[15, 3], [40, 5], [70, 7]])
    monster_chances['skeleton'] = from_dungeon_level([[30, 5], [40, 8], [70, 10]])
    monster_chances['Evil'] = from_dungeon_level([[25, 7], [45, 10]])
    
    #Max item numbers and wut not
    max_items = from_dungeon_level([[1, 1], [2, 6]])
    
    #item chance
    item_chances = {}
    item_chances['heal'] = 15
    item_chances['lightning'] = from_dungeon_level([[15, 4]])
    item_chances['fireball'] = from_dungeon_level([[15, 6]])
    item_chances['confuse'] = from_dungeon_level([[5, 2]])
    item_chances['r_axe'] = from_dungeon_level([[25, 1], [0, 5]])
    item_chances['l_axe'] = from_dungeon_level([[25, 1], [0, 6]])
    item_chances['shield'] = from_dungeon_level([[25, 1], [0, 5]])
    item_chances['r_axe+1'] = from_dungeon_level([[20, 5]])
    item_chances['shield+1'] = from_dungeon_level([[25, 5]])
    item_chances['Plate'] = from_dungeon_level([[20, 3]])
    item_chances['Leather'] = from_dungeon_level([[30, 1], [0, 6]])
    
    num_monsters = libtcod.random_get_int(0,0, max_monsters)
    
    for i in range(num_monsters):
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)
    
        if not is_blocked(x, y):
            choice = random_choice(monster_chances)
            if choice == 'orc':
                #ORCS ARE AT THE GATES
                fighter_component = Fighter(hp = 20, defense = 1, power = 4, xp = 35, death_function = monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'o', 'orc', libtcod.desaturated_green, blocks = True, fighter = fighter_component, ai = ai_component)
            elif choice == 'orc2':
                #ORCS ARE AT THE GATES x2
                fighter_component = Fighter(hp = 25, defense = 2, power = 6, xp = 75, death_function = monster_death)
                ai_component = BasicMonster()                
                monster = Object(x, y, 'O', 'Orc+1', libtcod.desaturated_green, blocks = True, fighter = fighter_component, ai = ai_component)
            elif choice == 'troll':
                # le sigh, they brought a cave troll
                fighter_component = Fighter(hp = 35, defense = 3, power = 8, xp = 100, death_function = monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'T', 'troll', libtcod.darker_green, blocks = True, fighter = fighter_component, ai = ai_component)

            elif choice == 'skeleton':
                #ahhhhhh!!!!!!!
                fighter_component = Fighter(hp = 100, defense = 5, power = 10, xp = 400, death_function = skeleton_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'S', 'skeleton', libtcod.white, blocks = True, fighter = fighter_component, ai = ai_component)
            elif choice == 'Evil':
                #??????
                fighter_component = Fighter(hp = 200, defense = 6, power = 13, xp = 650, death_function = skeleton_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'W', 'Pure Evil', libtcod.flame, blocks = True, fighter = fighter_component, ai = ai_component)
                
            objects.append(monster)
    num_items = libtcod.random_get_int(0, 0, max_items)
    for i in range(num_items):
        #choose random spot for item
        x = libtcod.random_get_int(0, room.x1+1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)
        
        #only place if not blocked
        if not is_blocked(x, y):
            choice = random_choice(item_chances)
            if choice == 'heal':
                #create heals
                item_component = Item(use_function = cast_heal)
                item = Object(x, y, '!', 'healing potion', libtcod.violet, item = item_component)
            elif choice == 'lightning':
                #create a lightning bolt scroll
                item_component = Item(use_function = cast_lightning)
                item = Object(x, y, '#', 'Scroll of Lightning Bolt', libtcod.light_red, item = item_component)
            elif choice == 'fireball':
                #create a fireball bolt scroll
                item_component = Item(use_function = cast_fireball)
                item = Object(x, y, '*', 'Scroll of FireBall', libtcod.light_red, item = item_component)
            elif choice == 'confuse':
                #create a confuse scroll
                item_component = Item(use_function = cast_confuse)
                item = Object(x, y, '#', 'Scroll of Confusion', libtcod.light_red, item = item_component)
            elif choice == 'r_axe':
                #create an axe!
                equipment_component = Equipment(slot = 'right hand', power_bonus = 3)
                item = Object(x, y, '7', 'R_Axe', libtcod.sky, equipment = equipment_component)
            elif choice == 'shield':
                #shields are for losers!
                equipment_component = Equipment(slot = 'left hand', defense_bonus = 1)
                item = Object(x, y, '[', 'shield', libtcod.darker_orange, equipment = equipment_component)
            elif choice == 'l_axe':
                #create an axe!
                equipment_component = Equipment(slot = 'left hand', power_bonus = 2)
                item = Object(x, y, '7', 'L_Axe', libtcod.orange, equipment = equipment_component)
            elif choice == 'shield+1':
                #shields are for losers!
                equipment_component = Equipment(slot = 'left hand', defense_bonus = 3)
                item = Object(x, y, '[', 'shield+1', libtcod.darker_orange, equipment = equipment_component)
            elif choice == 'r_axe+1':
                #create an axe!
                equipment_component = Equipment(slot = 'right hand', power_bonus = 5)
                item = Object(x, y, '7', 'R_Axe+1', libtcod.sky, equipment = equipment_component)
            elif choice == 'Plate':
                #BIG ARMOR
                equipment_component = Equipment(slot = 'body', defense_bonus = 3, max_hp_bonus = 50, power_bonus = - 1)
                item = Object(x, y, 'Y', 'Plate', libtcod.silver, equipment = equipment_component)
            elif choice == 'Leather':
                #Little armor...
                equipment_component = Equipment(slot = 'body', defense_bonus = 1, max_hp_bonus = 25)
                item = Object(x, y, 'A', 'Leather', libtcod.sepia, equipment = equipment_component)                        
            objects.append(item)
            item.send_to_back()
            item.always_visible = True


                
def create_room(room):
    global map
    #go through the tiles in the rectangle and make them passable
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False
            
            
########### Rendering Functions!

def render_all():
    global color_dark_wall, color_light_wall, fov_map
    global color_dark_ground, color_light_ground
    global fov_recompute
    
    if fov_recompute:
        fov_recompute = False
        libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)


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
    
    #draw all objects in the list
    for object in objects:
        if object != player:
            object.draw()
    player.draw()    
    
    
    libtcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)
    
    libtcod.console_set_default_background(panel, libtcod.black)
    libtcod.console_clear(panel)
    
    y = 1
    for (line, color) in game_msgs:
        libtcod.console_set_default_foreground(panel, color)
        libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
        y += 1
    
    #show stats
    render_bar(1, 2, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp, libtcod.light_red, libtcod.darker_red)
    libtcod.console_print_ex(panel, 1, 1, libtcod.BKGND_NONE, libtcod.LEFT, 'Dungeon level ' + str(dungeon_level))
    render_bar(1, 3, BAR_WIDTH, 'XP', player.fighter.xp, (LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR), libtcod.light_blue, libtcod.dark_blue)
    libtcod.console_print_ex(panel, 1, 4, libtcod.BKGND_NONE, libtcod.LEFT, 'Player Level: ' + str(player.level))
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
    if header == '':
        header_height = 0
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
    
    if key.vk == libtcod.KEY_ENTER and key.lalt:
        #Alt + Enter: toggle fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
    
    index = key.c - ord('a')
    if index >= 0 and index < len(options): return index
    return None

def inventory_menu(header):
    #show menu
    if len(inventory) == 0:
        options = ['Inventory is empty']
    else:
        options = []
        for item in inventory:
            text = item.name
            #show additional info
            if item.equipment and item.equipment.is_equipped:
                text = text + ' (on ' + item.equipment.slot + ')'
            options.append(text)
    
    index = menu(header, options, INVENTORY_WIDTH)
    if index is None or len(inventory) == 0: return None
    return inventory[index].item

def skill_menu(header):
    #show menu
    if len(skills) == 0:
        options = ['You have no skills!']
    else:
        options = []
        for skill in skills:
            text = skill.name
            options.append(text)
    index = menu(header, options, INVENTORY_WIDTH)
    if index is None or len(skills) == 0: return None
    return skills[index]
    
def main_menu():
    img = libtcod.image_load('menu_background1.png')
    while not libtcod.console_is_window_closed():
    
        libtcod.image_blit_2x(img, 0, 0, 0)        
        libtcod.console_set_default_foreground(0, libtcod.light_yellow)
        libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, libtcod.BKGND_NONE, libtcod.CENTER, 'SHENANIGAN TOMBS OF SHENANIGANS')
        libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT-2, libtcod.BKGND_NONE, libtcod.CENTER, 'By Feil')
        
        choice = menu('', ['Play a new game', 'Continue last game', 'Quit'], 24)
        
        if choice == 0:
            new_game()
            play_game()
        elif choice == 2:
            break
        elif choice == 1:
            try:
                load_game()
            except:
                msgbox('\n No saved game to load.\n', 24)
                continue
            play_game()
 
def random_choice_index(chances):
    #choose some options
    dice = libtcod.random_get_int(0, 1, sum(chances))
    
    #go through all chances keeping sums
    running_sum = 0
    choice = 0
    for w in chances:
        running_sum += w
        
        #check the dice
        if dice <= running_sum:
            return choice
        choice += 1

def random_choice(chances_dict):
    chances = chances_dict.values()
    strings = chances_dict.keys()
    
    return strings[random_choice_index(chances)]
        
############## Game Operations!


def handle_keys():
    global fov_recompute, game_state
    global key
    
    if key.vk == libtcod.KEY_ENTER and key.lalt:
        #Alt + Enter: toggle fullscreen
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
    
    elif key.vk == libtcod.KEY_ESCAPE:
        return 'exit' #exit game    
    
    
    #movement keys
    if game_state == 'playing':
        '''if key.vk == libtcod.KEY_UP:
            player_move_or_attack(0, -1)

        elif key.vk == libtcod.KEY_DOWN:
            player_move_or_attack(0, 1)
        
        elif key.vk == libtcod.KEY_LEFT:
            player_move_or_attack(-1, 0)
        
        elif key.vk == libtcod.KEY_RIGHT:
            player_move_or_attack(1, 0)'''
        
        if key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8:
            player_move_or_attack(0, -1)
        elif key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2:
            player_move_or_attack(0, 1)
        elif key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4:
            player_move_or_attack(-1, 0)
        elif key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6:
            player_move_or_attack(1, 0)
        elif key.vk == libtcod.KEY_HOME or key.vk == libtcod.KEY_KP7:
            player_move_or_attack(-1, -1)
        elif key.vk == libtcod.KEY_PAGEUP or key.vk == libtcod.KEY_KP9:
            player_move_or_attack(1, -1)
        elif key.vk == libtcod.KEY_END or key.vk == libtcod.KEY_KP1:
            player_move_or_attack(-1, 1)
        elif key.vk == libtcod.KEY_PAGEDOWN or key.vk == libtcod.KEY_KP3:
            player_move_or_attack(1, 1)
        elif key.vk == libtcod.KEY_KP5:
            pass  #do nothing ie wait for the monster to come to you
        
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
            if key_char == 'd':
                chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.drop()
            if key_char == 'k':
                chosen_skill = skill_menu('Press the key next to a skill to use it!')
                if chosen_skill is not None:
                    chosen_skill.use()
            
            if key_char == '<':
                #go down stairs
                if stairs.x == player.x and stairs.y == player.y:
                    next_level()
                    
            if key_char == 'c':
                #Show character information
                level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
                msgbox('Character Information\n\nLevel: ' + str(player.level) + '\nExperience: ' + str(player.fighter.xp) +
                    '\nExperience to level up: ' + str(level_up_xp) + '\n\nMaximum HP: ' + str(player.fighter.max_hp) +
                    '\nAttack: ' + str(player.fighter.power) + '\nDefense: ' + str(player.fighter.defense), CHARACTER_SCREEN_WIDTH)

                    
            return 'didnt-take-turn'
        

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
    message(monster.name.capitalize() + ' is dead! You gain ' + str(monster.fighter.xp) + ' experience points!')
    monster.char = '%'
    monster.color = libtcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of ' + monster.name
    monster.send_to_back()
    dice = libtcod.random_get_int(0, 1, 100)
    if dice > 75:
        item_component = Item(use_function = cast_heal)
        item = Object(monster.x, monster.y, '!', 'healing potion', libtcod.violet, item = item_component)
        objects.append(item)
        item.always_visible = True
        message(monster.name + ' dropped something!')

def skeleton_death(monster):
    global objects
    message(monster.name.capitalize() + ' is dead! You gain ' + str(monster.fighter.xp) + ' experience points!')
    monster.char = '%'
    monster.color = libtcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of ' + monster.name
    monster.send_to_back()
    dice = libtcod.random_get_int(0, 1, 100)
    if dice > 50:
        equipment_component = Equipment(slot = 'right hand', power_bonus = 7)
        item = Object(monster.x, monster.y, 'P', 'R_Axe+3', libtcod.gold, equipment = equipment_component)
        objects.append(item)
        item.always_visible = True
        message(monster.name + ' dropped something!')
    elif dice > 75:
        equipment_component = Equipment(slot = 'left hand', power_bonus = 5)
        item = Object(monster.x, monster.y, 'P', 'L_Axe+3', libtcod.brass, equipment = equipment_component)
        objects.append(item)
        item.always_visible = True
        message(monster.name + ' dropped something!')

        
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

def target_tile(max_range = None):
    #return the position of a tile selected by player
    global key, mouse
    while True:
        #render screen doh
        libtcod.console_flush()
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)
        render_all()
        
        (x, y) = (mouse.cx, mouse.cy)
        
        if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and (max_range is None or player.distance(x, y) <= max_range)):
            return(x, y)
            
        if mouse.rbutton_pressed:
            return (None, None)
            
def save_game():
    file = shelve.open('savegame', 'n')
    file['map'] = map
    file['objects'] = objects
    file['player_index'] = objects.index(player)
    file['inventory'] = inventory
    file['game_msgs'] = game_msgs
    file['game_state'] = game_state
    file['stairs_index'] = objects.index(stairs)
    file['dungeon_level'] = dungeon_level
    file['skills'] = skills
    file.close()

def load_game():
    #Load previous game
    global map, objects, player, inventory, game_msgs, game_state, stairs, dungeon_level, skills
    
    file = shelve.open('savegame', 'r')
    map = file['map']
    objects = file['objects']
    player = objects[file['player_index']]
    inventory = file['inventory']
    game_msgs = file['game_msgs']
    game_state = file['game_state']
    stairs = objects[file['stairs_index']]
    dungeon_level = file['dungeon_level']
    skills = file['skills']
    file.close()
    
    initialize_fov()
    
def target_monster(max_range=None):
    #returns a clicked monster inside the FOV upto a range
    while True:
        (x, y) = target_tile(max_range)
        if x is None:
            return None
        
        for obj in objects:
            if obj.x == x and obj.y == y and obj.fighter and obj != player:
                return obj
                
def msgbox(text, width = 50):
    menu(text, [], width)

def next_level():
    global dungeon_level

    #advance to the next level
    message('You take a moment to rest and recover your strength.', libtcod.light_violet)
    player.fighter.heal(player.fighter.max_hp /2)
    
    message('After a rare moment fo peace, you descend deeper into the heart of the dungeon...', libtcod.red)
    make_map()
    initialize_fov()
    dungeon_level += 1

def check_level_up():
    global skills
    #see if the player bossed up
    level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
    if player.fighter.xp >= level_up_xp:
        #DA DA DAHHHH
        player.level += 1
        player.fighter.xp -= level_up_xp
        message('You is a boss! You reached level ' + str(player.level) + '!', libtcod.yellow)
    
        choice = None
        while choice == None:
            choice = menu('Level up! Choose a stat to raise: \n', ['Constitution (+20 HP)', 'Strength (+1 attack)', 'Agility (+1 Defense)'], LEVEL_SCREEN_WIDTH)
            
        if choice == 0:
            player.fighter.base_max_hp += 20
            player.fighter.hp += 20
        elif choice == 1:
            player.fighter.base_power += 1
        elif choice == 2:
            player.fighter.base_defense += 1
        
        if player.level == 2:
            sword_spin = Skill('Sword Spin', use_function = spin_move)
            skills.append(sword_spin)
        
        if player.level == 5:
            def_buff = Skill('Armour of Courage', use_function = defense_buff)
            skills.append(def_buff)
            
def from_dungeon_level(table):
    #returns a value dependent on a level!
    for (value, level) in reversed(table):
        if dungeon_level >= level:
            return value
    return 0
    
def get_equipped_in_slot(slot):
    #returns items in slot, or None if necessary
    for obj in inventory:
        if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
            return obj.equipment
    return None

def get_all_equipped(obj):
    if obj == player:
        equipped_list = []
        for item in inventory:
            if item.equipment and item.equipment.is_equipped:
                equipped_list.append(item.equipment)
        return equipped_list
    else:
        return []
    
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
    #find monster to confuse
    message('Left-click an enemy to confuse it, or right-click to cancel.', libtcod.light_cyan)
    monster = target_monster(CONFUSE_RANGE)
    if monster is None: return 'cancelled'
        
    old_ai = monster.ai
    monster.ai = ConfusedMonster(old_ai)
    monster.ai.owner = monster
    message('The eyes of the ' + monster.name + ' look vacant, as he starts to stumble around!', libtcod.light_green)
    
def cast_fireball():
    #find target, destroy.
    message('Left-click a target tile for the fireball, or right click to cancel', libtcod.light_cyan)
    (x, y) = target_tile()
    if x is None: return 'cancelled'
    message('The fireball explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!', libtcod.orange)
        
    for obj in objects:
        if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
            message('The ' + obj.name + ' gets burned for ' + str(FIREBALL_DAMAGE) + ' hit points.', libtcod.orange)
            obj.fighter.take_damage(FIREBALL_DAMAGE)

def spin_move():
    #HYAH HEY HYEAHHHHHHH
    message('You swing your sword wildly about the area damaging all monsters in range!')
    
    skill_power = player.fighter.power + 1
    
    for obj in objects:
        if obj.distance(player.x, player.y) <= 2 and obj.fighter and obj != player:
            skill_damage = skill_power - obj.fighter.defense
            message('The ' + obj.name + ' takes ' + str(skill_damage) + ' damage!', libtcod.orange)
            obj.fighter.take_damage(skill_damage)
    message('The attack took some strength out of you! You take ' + str(PLAYER_SKILL_DAMAGE) + 'damage!', libtcod.flame)
    player.fighter.take_damage(PLAYER_SKILL_DAMAGE)

def defense_buff():
    #Cast Protect Self
    global is_buff_active
    
    if not is_buff_active:
        message('Your fortitude and courage has influenced your agility!', libtcod.sky)
        message('Your defense increases by ' + BUFF_AMOUNT, libtcod.sky)
        player.fighter.base_defense += BUFF_AMOUNT
        is_buff_active = True
    else:
        message('The defense buff is already active!', libtcod.red)
        
    
    
#############################
#   Pre-Loop Declaration    #
#############################


libtcod.console_set_custom_font('arial10x10.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD) #SET FONT

libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'python/libtcod tutorial', False) #INITIALIZE
con = libtcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

libtcod.sys_set_fps(LIMIT_FPS) #SET FPS

def new_game():
    global player, inventory, game_msgs, game_state, dungeon_level, skills
    
    dungeon_level = 1
    
    fighter_component = Fighter(hp = 100, defense = 1, power = 4, xp = 0, death_function = player_death)    
    player = Object(0, 0, 'W', 'player', libtcod.white, blocks = True, fighter = fighter_component)

    player.level = 1
    
    make_map()
    initialize_fov()
    game_state = 'playing'
    
    game_msgs = [] 
    inventory = []
    skills = []
    is_buff_active = False
    
    message('Welcome stranger! Prepare to face danger and doom!', libtcod.red)

def initialize_fov():
    global fov_recompute, fov_map
    fov_recompute = True

    
    fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)
    
    libtcod.console_clear(con)            
            

def play_game():
    global key, mouse
    
    player_action = None

    #setup for GUI
    panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

        
    mouse = libtcod.Mouse()
    key = libtcod.Key()

    while not libtcod.console_is_window_closed():
        libtcod.console_set_default_foreground(con, libtcod.white)
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)
        
        render_all()
        
        libtcod.console_flush()
        check_level_up()
        for object in objects:
            object.clear()
        #handle keys and exit game if necessary
        player_action = handle_keys()
        
        if game_state == 'playing' and player_action != 'didnt-take-turn':
            for object in objects:
                if object.ai:
                    object.ai.take_turn()
                    
        
        if player_action == 'exit':
            save_game()
            break
main_menu()