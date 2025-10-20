
import pygame
import random
import math
import io
import wave
from array import array

# --------- Configuration ---------
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
FPS = 60

PADDLE_WIDTH = 120
PADDLE_HEIGHT = 18
PADDLE_Y_OFFSET = 48
BALL_RADIUS = 9
BRICK_ROWS_BASE = 6
BRICK_COLS = 12
BRICK_AREA_MARGIN = 70
BRICK_WIDTH = (SCREEN_WIDTH - 140) // BRICK_COLS
BRICK_HEIGHT = 26
POWERUP_CHANCE = 0.18
BOMB_BRICK_CHANCE = 0.15  # 15% chance to be a bomb brick
MAX_LEVEL = 1000

POWER_TYPES = ['EXPAND', 'MULTI', 'SLOW', 'LIFE', 'STICKY', 'REVERSE']
POWER_DURATION = 12.0
REVERSE_DURATION = 5.0

WHITE = (255,255,255)
BLACK = (0,0,0)
GREY = (200,200,200)
BLUE = (60,140,220)
GREEN = (90,200,120)
RED = (220,80,80)
ORANGE = (230,130,70)
BG = (10,10,18)

BASE_SPEED = 5.0

# --------- Sound helpers (in-memory beeps) ---------
def make_beep(freq=440, duration_ms=120, volume=0.5, sample_rate=22050):
    try:
        n_samples = int(sample_rate * duration_ms / 1000)
        buf = array('h')
        max_amp = int(32767 * volume)
        for i in range(n_samples):
            t = i / sample_rate
            sample = int(max_amp * math.sin(2 * math.pi * freq * t))
            buf.append(sample)
        bio = io.BytesIO()
        wf = wave.open(bio, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(buf.tobytes())
        wf.close()
        bio.seek(0)
        return pygame.mixer.Sound(file=bio)
    except Exception:
        return None

def play_explosion(sfx_list):
    for s in sfx_list:
        if s:
            s.play()

# --------- Game objects ---------
class Paddle:
    def __init__(self):
        self.width = PADDLE_WIDTH
        self.height = PADDLE_HEIGHT
        self.x = (SCREEN_WIDTH - self.width) // 2
        self.y = SCREEN_HEIGHT - PADDLE_Y_OFFSET
        self.speed = 10

    def rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)

    def move(self, dx):
        self.x += dx * self.speed
        self.x = max(0, min(SCREEN_WIDTH - self.width, self.x))

    def draw(self, surf):
        # rounded paddle with gradient and glow
        rect = self.rect()
        pygame.draw.rect(surf, (30,120,220), rect, border_radius=12)
        inner = rect.inflate(-6, -6)
        pygame.draw.rect(surf, (120,200,255), inner, border_radius=10)
        pygame.draw.rect(surf, WHITE, rect, 2, border_radius=12)

class Ball:
    def __init__(self, x, y, vx=None, vy=None):
        self.x = x
        self.y = y
        angle = random.uniform(-1.0, 1.0)
        speed = BASE_SPEED
        self.vx = vx if vx is not None else (angle * speed)
        self.vy = vy if vy is not None else -abs(speed)
        self.radius = BALL_RADIUS
        self.stuck = True
        self.trail = []

    def rect(self):
        return pygame.Rect(int(self.x-self.radius), int(self.y-self.radius), self.radius*2, self.radius*2)

    def update(self, dt):
        if self.stuck:
            return
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.x - self.radius <= 0:
            self.x = self.radius
            self.vx *= -1
        if self.x + self.radius >= SCREEN_WIDTH:
            self.x = SCREEN_WIDTH - self.radius
            self.vx *= -1
        if self.y - self.radius <= 0:
            self.y = self.radius
            self.vy *= -1
        self.trail.insert(0, (self.x, self.y))
        if len(self.trail) > 12:
            self.trail.pop()

    def draw(self, surf):
        glow_surf = pygame.Surface((self.radius*8, self.radius*8), pygame.SRCALPHA)
        gx = glow_surf.get_width()//2
        gy = glow_surf.get_height()//2
        for i, alpha in enumerate([20, 40, 70, 110]):
            pygame.draw.circle(glow_surf, (120,200,255,alpha), (gx, gy), self.radius*2 + i*4)
        surf.blit(glow_surf, (int(self.x - gx), int(self.y - gy)), special_flags=pygame.BLEND_PREMULTIPLIED)
        for i, (tx,ty) in enumerate(self.trail):
            a = max(10, 120 - i*10)
            r = max(2, self.radius - i//3)
            trail_surf = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
            pygame.draw.circle(trail_surf, (200,230,255,a), (r,r), r)
            surf.blit(trail_surf, (int(tx-r), int(ty-r)))
        pygame.draw.circle(surf, WHITE, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(surf, (200,240,255), (int(self.x-2), int(self.y-2)), max(1, self.radius//2))

class Brick:
    def __init__(self, row, col, x, y, w, h, hits=1, color=(180,80,80), kind='normal'):
        self.row = row
        self.col = col
        self.rect = pygame.Rect(x,y,w,h)
        self.hits = hits
        self.color = color
        self.kind = kind

    def draw(self, surf):
        box = self.rect
        base = self.color
        inner = box.inflate(-4, -4)
        pygame.draw.rect(surf, (max(0,base[0]-30), max(0,base[1]-30), max(0,base[2]-30)), box, border_radius=6)
        pygame.draw.rect(surf, base, inner, border_radius=6)
        pygame.draw.rect(surf, BLACK, box, 2, border_radius=6)
        if self.kind == 'bomb':
            font = pygame.font.SysFont(None, 20)
            t = font.render('B', True, BLACK)
            surf.blit(t, (box.centerx - t.get_width()//2, box.centery - t.get_height()//2))

class PowerUp:
    SIZE = 26
    SPEED = 2.6
    ICONS = {
        'EXPAND': '—',
        'MULTI': '*',
        'SLOW': '~',
        'LIFE': '+',
        'STICKY': 'S',
        'REVERSE': '<>'
    }
    def __init__(self, x, y, kind):
        self.x = x
        self.y = y
        self.kind = kind
        self.rect = pygame.Rect(x, y, PowerUp.SIZE, PowerUp.SIZE)

    def update(self, dt):
        self.y += PowerUp.SPEED * dt
        self.rect.topleft = (int(self.x), int(self.y))

    def draw(self, surf):
        col = {
            'EXPAND': (120,180,255),
            'MULTI': (255,200,80),
            'SLOW': (150,150,255),
            'LIFE': (90,220,140),
            'STICKY': (200,160,255),
            'REVERSE': (255,110,110)
        }.get(self.kind, WHITE)
        r = pygame.Rect(int(self.x), int(self.y), PowerUp.SIZE, PowerUp.SIZE)
        pygame.draw.rect(surf, (max(0,col[0]-20),max(0,col[1]-20),max(0,col[2]-20)), r, border_radius=6)
        pygame.draw.rect(surf, col, r.inflate(-6,-6), border_radius=5)
        pygame.draw.rect(surf, WHITE, r, 2, border_radius=6)
        font = pygame.font.SysFont(None, 20)
        txt = font.render(PowerUp.ICONS.get(self.kind, '?'), True, BLACK)
        surf.blit(txt, (r.centerx - txt.get_width()//2, r.centery - txt.get_height()//2))

# --------- Helpers ---------

def create_bricks(level_rows):
    bricks = []
    margin_x = BRICK_AREA_MARGIN
    start_y = 90
    for row in range(level_rows):
        pattern = [1]*BRICK_COLS
        for g in range(random.randint(0,3)):
            idx = random.randrange(BRICK_COLS)
            pattern[idx] = 0
        if random.random() < 0.4:
            random.shuffle(pattern)
        for col in range(BRICK_COLS):
            if pattern[col] == 0:
                continue
            x = margin_x + col * BRICK_WIDTH
            y = start_y + row * BRICK_HEIGHT
            hits = 1 + (1 if random.random() < 0.12 else 0)
            kind = 'bomb' if random.random() < BOMB_BRICK_CHANCE else 'normal'
            color = row_color(row, level_rows) if kind=='normal' else ORANGE
            bricks.append(Brick(row, col, x, y, BRICK_WIDTH-6, BRICK_HEIGHT-6, hits, color, kind))
    return bricks

def row_color(row, total_rows):
    palettes = [ (200,90,90), (230,150,90), (200,200,90), (120,200,140), (100,160,230), (160,120,220) ]
    return palettes[row % len(palettes)]

def explode_brick(target, bricks, score_ref):
    to_check = [(target.row, target.col)]
    destroyed = []
    while to_check:
        r,c = to_check.pop()
        for b in list(bricks):
            if b.row == r and b.col == c:
                destroyed.append(b)
                try:
                    bricks.remove(b)
                except ValueError:
                    pass
                score_ref[0] += 15
                if b.kind == 'bomb':
                    neighbors = [(r-1,c),(r+1,c),(r,c-1),(r,c+1)]
                    for nr,nc in neighbors:
                        to_check.append((nr,nc))
                break
    return destroyed

# --------- UI Button helper ---------
class Button:
    def __init__(self, rect, label):
        self.rect = pygame.Rect(rect)
        self.label = label

    def draw(self, surf, bg=(40,40,60), fg=WHITE):
        pygame.draw.rect(surf, bg, self.rect, border_radius=10)
        pygame.draw.rect(surf, WHITE, self.rect, 2, border_radius=10)
        font = pygame.font.SysFont(None, 22)
        txt = font.render(self.label, True, fg)
        surf.blit(txt, (self.rect.x + (self.rect.width - txt.get_width())//2, self.rect.y + (self.rect.height - txt.get_height())//2))

    def clicked(self, pos):
        return self.rect.collidepoint(pos)

# --------- Game Class (main) ---------
class Game:
    def __init__(self):
        pygame.init()
        pygame.mixer.init(frequency=22050)
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption('Brick Breaker — Visual Upgrade (1024x768)')
        self.clock = pygame.time.Clock()
        self.running = True

        # sounds
        self.sound_on = True
        self.sfx_beep = make_beep(880, 70, 0.4)
        self.sfx_pop = make_beep(650, 60, 0.35)
        self.sfx_power = make_beep(1000, 90, 0.45)
        self.sfx_ex1 = make_beep(200, 120, 0.6)
        self.sfx_ex2 = make_beep(420, 160, 0.5)

        # background particles (stars)
        self.stars = [{'x': random.randint(0,SCREEN_WIDTH), 'y': random.randint(0,SCREEN_HEIGHT), 'r': random.choice([1,2,2])} for _ in range(100)]

        # day/night + weather state
        self.time_of_day = 0.0  # 0..1 loop (0 morning, 0.5 night)
        self.cycle_speed = 1/ (45 * FPS)  # full cycle ~45 seconds
        self.weather = 'clear'  # clear, clouds, rain
        self.weather_timer = random.randint(8*FPS, 18*FPS)
        self.clouds = []  # list of cloud dicts
        self.rain = []    # list of raindrops
        self.lightning_timer = 0

        # state
        self.state = 'menu'
        self.level = 1
        self.best_level = 1
        self.lives = 3
        self.score = 0
        self.active_powers = {}
        self.is_reversed = False

        self.font = pygame.font.SysFont(None, 20)
        self.menu_buttons = []
        self.settings_buttons = []
        self.popup_buttons = []

        self.reset_level(first=True)

    def reset_level(self, first=False):
        self.paddle = Paddle()
        self.balls = [Ball(self.paddle.x + self.paddle.width//2, self.paddle.y - BALL_RADIUS - 2)]
        for b in self.balls:
            b.stuck = True
        rows = BRICK_ROWS_BASE + (self.level // 3)
        self.bricks = create_bricks(rows)
        self.powerups = []
        self.show_level_popup = not first
        self.popup_message = f'Level {self.level}'

    def restart_game(self):
        self.level = 1
        self.score = 0
        self.lives = 3
        self.active_powers.clear()
        self.is_reversed = False
        self.reset_level(first=True)
        self.state = 'playing'

    def spawn_power(self, x, y):
        if random.random() < POWERUP_CHANCE:
            self.powerups.append(PowerUp(x-12, y-12, random.choice(POWER_TYPES)))

    def apply_power(self, kind):
        if kind == 'REVERSE':
            self.active_powers[kind] = REVERSE_DURATION
            self.is_reversed = True
        else:
            self.active_powers[kind] = POWER_DURATION
        if kind == 'EXPAND':
            self.paddle.width = min(400, int(self.paddle.width * 1.5))
        elif kind == 'MULTI':
            new_balls = []
            existing = list(self.balls)
            for b in existing:
                nb1 = Ball(b.x, b.y, (b.vx if b.vx!=0 else BASE_SPEED), b.vy)
                nb2 = Ball(b.x, b.y, -(b.vx if b.vx!=0 else BASE_SPEED), b.vy)
                nb1.stuck = False
                nb2.stuck = False
                new_balls.extend([nb1, nb2])
            self.balls.extend(new_balls)
        elif kind == 'SLOW':
            for b in self.balls:
                b.vx *= 0.6
                b.vy *= 0.6
        elif kind == 'LIFE':
            self.lives += 1
        elif kind == 'STICKY':
            self.active_powers[kind] = POWER_DURATION
        if self.sound_on and self.sfx_power:
            self.sfx_power.play()

    def remove_power(self, kind):
        if kind == 'EXPAND':
            self.paddle.width = PADDLE_WIDTH
        if kind == 'SLOW':
            for b in self.balls:
                b.vx *= (1/0.6)
                b.vy *= (1/0.6)
        if kind == 'REVERSE':
            self.is_reversed = False
        if kind in self.active_powers:
            del self.active_powers[kind]

    def handle_collisions(self):
        for b in list(self.balls):
            if b.stuck:
                b.x = self.paddle.x + self.paddle.width//2
                b.y = self.paddle.y - b.radius - 2
            if b.rect().colliderect(self.paddle.rect()) and not b.stuck:
                if 'STICKY' in self.active_powers:
                    b.stuck = True
                    b.vx = 0
                    b.vy = 0
                else:
                    b.y = self.paddle.y - b.radius - 1
                    b.vy *= -1
                    offset = (b.x - (self.paddle.x + self.paddle.width/2)) / (self.paddle.width/2)
                    b.vx += offset * 3
                if self.sound_on and self.sfx_beep:
                    self.sfx_beep.play()
            for brick in list(self.bricks):
                if b.rect().colliderect(brick.rect):
                    overlap = b.rect().clip(brick.rect)
                    if overlap.width < overlap.height:
                        b.vx *= -1
                    else:
                        b.vy *= -1
                    brick.hits -= 1
                    if brick.hits <= 0:
                        if brick.kind == 'bomb':
                            destroyed = explode_brick(brick, self.bricks, [self.score])
                            if self.sound_on:
                                play_explosion([self.sfx_ex1, self.sfx_ex2])
                        else:
                            self.score += 10
                            try:
                                self.bricks.remove(brick)
                            except ValueError:
                                pass
                            self.spawn_power(brick.rect.centerx, brick.rect.centery)
                    else:
                        if self.sound_on and self.sfx_pop:
                            self.sfx_pop.play()
                    break
        for p in list(self.powerups):
            p.update(1)
            if p.rect.colliderect(self.paddle.rect()):
                self.apply_power(p.kind)
                try:
                    self.powerups.remove(p)
                except ValueError:
                    pass
        self.powerups = [p for p in self.powerups if p.y < SCREEN_HEIGHT+50]

    def update(self, dt):
        # advance time-of-day and weather timers (visual only)
        self.time_of_day = (self.time_of_day + self.cycle_speed * dt) % 1.0
        # weather timer counts down; when zero, randomize weather and reset timer
        self.weather_timer -= 1
        if self.weather_timer <= 0:
            self.weather = random.choices(['clear','clouds','rain'], weights=[0.6,0.3,0.1])[0]
            self.weather_timer = random.randint(8*FPS, 20*FPS)
            # spawn some clouds if needed
            self.clouds = []
            if self.weather in ('clouds','rain'):
                for i in range(random.randint(3,7)):
                    self.clouds.append({'x': random.randint(-200, SCREEN_WIDTH), 'y': random.randint(20, 160), 'w': random.randint(160,320), 'speed': random.uniform(0.12,0.4)})
            # start rain drops if rain
            self.rain = []
            if self.weather == 'rain':
                for i in range(160):
                    self.rain.append({'x': random.randint(0, SCREEN_WIDTH), 'y': random.randint(-SCREEN_HEIGHT, SCREEN_HEIGHT), 'len': random.randint(8,18), 'speed': random.uniform(2.0,4.0)})
            # lightning chance
            if self.weather == 'rain' and random.random() < 0.25:
                self.lightning_timer = random.randint(2, 6)

        # lightning countdown (short flashes)
        if self.lightning_timer > 0:
            self.lightning_timer -= 1
            if self.lightning_timer == 0 and random.random() < 0.35:
                self.lightning_timer = random.randint(2,6)

        # input
        keys = pygame.key.get_pressed()
        left_pressed = keys[pygame.K_LEFT]
        right_pressed = keys[pygame.K_RIGHT]
        if self.is_reversed:
            left_pressed, right_pressed = right_pressed, left_pressed
        if left_pressed:
            self.paddle.move(-1)
        if right_pressed:
            self.paddle.move(1)

        for b in list(self.balls):
            if b.stuck:
                b.x = self.paddle.x + self.paddle.width//2
                b.y = self.paddle.y - b.radius - 2
            b.update(dt)
            if b.y - b.radius > SCREEN_HEIGHT:
                try:
                    self.balls.remove(b)
                except ValueError:
                    pass
        if len(self.balls) == 0:
            self.lives -= 1
            if self.lives <= 0:
                self.state = 'game_over'
                return
            else:
                self.balls = [Ball(self.paddle.x + self.paddle.width//2, self.paddle.y - BALL_RADIUS - 2)]
        to_remove = []
        for k in list(self.active_powers.keys()):
            decay = REVERSE_DURATION if k == 'REVERSE' else POWER_DURATION
            self.active_powers[k] -= dt / FPS * (REVERSE_DURATION/REVERSE_DURATION if k=='REVERSE' else POWER_DURATION/POWER_DURATION)
            if self.active_powers[k] <= 0:
                to_remove.append(k)
        for k in to_remove:
            self.remove_power(k)
        for p in self.powerups:
            p.update(dt)
        self.handle_collisions()
        if len(self.bricks) == 0 and self.state == 'playing':
            if self.level < MAX_LEVEL:
                self.state = 'level_popup'
                self.popup_message = f'Level {self.level} Cleared!'
                if self.level > self.best_level:
                    self.best_level = self.level
            else:
                self.state = 'max_popup'
                self.popup_message = f"You've reached the Max Level ({MAX_LEVEL})!"
                self.popup_sub = f"Best Level: {self.best_level}"

    # ---------- Visual/UI helpers ----------
    def lerp(self, a, b, t):
        return (int(a[0]*(1-t) + b[0]*t), int(a[1]*(1-t) + b[1]*t), int(a[2]*(1-t) + b[2]*t))

    def draw_background(self):
        # sky color based on time_of_day (0..1). We'll make cycle: morning(0) -> day(0.25) -> sunset(0.45) -> night(0.65) -> dawn(0.9) -> morning
        t = self.time_of_day
        if t < 0.25:  # morning -> day
            local_t = t / 0.25
            top = self.lerp((90,140,220), (120,180,255), local_t)
            bottom = self.lerp((200,220,255), (240,245,255), local_t)
        elif t < 0.45:  # day -> sunset
            local_t = (t-0.25) / 0.2
            top = self.lerp((120,180,255), (240,140,80), local_t)
            bottom = self.lerp((240,245,255), (250,200,140), local_t)
        elif t < 0.65:  # sunset -> night
            local_t = (t-0.45) / 0.2
            top = self.lerp((240,140,80), (20,30,60), local_t)
            bottom = self.lerp((250,200,140), (6,10,30), local_t)
        elif t < 0.9:  # night -> dawn
            local_t = (t-0.65) / 0.25
            top = self.lerp((20,30,60), (140,100,180), local_t)
            bottom = self.lerp((6,10,30), (200,150,200), local_t)
        else:  # dawn -> morning
            local_t = (t-0.9) / 0.1
            top = self.lerp((140,100,180), (90,140,220), local_t)
            bottom = self.lerp((200,150,200), (200,220,255), local_t)

        # vertical gradient
        for i in range(SCREEN_HEIGHT):
            tt = i / SCREEN_HEIGHT
            col = (int(top[0]*(1-tt) + bottom[0]*tt), int(top[1]*(1-tt) + bottom[1]*tt), int(top[2]*(1-tt) + bottom[2]*tt))
            pygame.draw.line(self.screen, col, (0,i), (SCREEN_WIDTH,i))

        # sun/moon position along an arc
        sun_x = int((SCREEN_WIDTH+200) * (0.1 + 0.8 * self.time_of_day)) - 100
        sun_y = int(120 + math.sin(self.time_of_day * math.pi * 2) * 100)
        if 0.05 < self.time_of_day < 0.55:
            # sun visible
            radius = 48
            glow = pygame.Surface((radius*6, radius*6), pygame.SRCALPHA)
            gx = glow.get_width()//2
            gy = glow.get_height()//2
            for i, a in enumerate([20,40,80,120]):
                pygame.draw.circle(glow, (255,220,140,a), (gx,gy), radius + i*8)
            self.screen.blit(glow, (sun_x - gx, sun_y - gy), special_flags=pygame.BLEND_PREMULTIPLIED)
            pygame.draw.circle(self.screen, (255,230,160), (sun_x, sun_y), radius)
        else:
            # moon + stars brighter at night
            radius = 32
            # small moon glow
            moon_surf = pygame.Surface((radius*4, radius*4), pygame.SRCALPHA)
            mgx = moon_surf.get_width()//2
            mgy = moon_surf.get_height()//2
            pygame.draw.circle(moon_surf, (220,230,255,140), (mgx,mgy), radius+6)
            self.screen.blit(moon_surf, (sun_x-mgx, sun_y-mgy))
            pygame.draw.circle(self.screen, (220,230,255), (sun_x, sun_y), radius)

        # stars (more visible at night)
        night_intensity = max(0.0, (0.5 - abs(self.time_of_day - 0.5)) * 2.0)
        for s in self.stars:
            alpha = int(180 * night_intensity)
            if alpha > 8:
                pygame.draw.circle(self.screen, (220,240,255), (int(s['x']), int(s['y'])), s['r'])
            s['y'] += 0.25 * (1 + 2*night_intensity)
            if s['y'] > SCREEN_HEIGHT:
                s['y'] = -2
                s['x'] = random.randint(0, SCREEN_WIDTH)

        # clouds
        if self.clouds:
            for c in self.clouds:
                rect = pygame.Rect(int(c['x']), int(c['y']), c['w'], 60)
                cloud_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
                # layered ellipses for soft cloud
                for i in range(5):
                    pygame.draw.ellipse(cloud_surf, (255,255,255,80), (i*10, 0, rect.width- i*20, rect.height))
                self.screen.blit(cloud_surf, rect.topleft)
                c['x'] += c['speed']
                if c['x'] > SCREEN_WIDTH + 200:
                    c['x'] = -c['w'] - 100

        # rain
        if self.weather == 'rain' and self.rain:
            for drop in self.rain:
                x = int(drop['x'])
                y = int(drop['y'])
                ln = drop['len']
                pygame.draw.line(self.screen, (180,200,230), (x, y), (x+2, y+ln), 1)
                drop['y'] += drop['speed']
                drop['x'] += 0.6
                if drop['y'] > SCREEN_HEIGHT:
                    drop['y'] = random.randint(-SCREEN_HEIGHT, -10)
                    drop['x'] = random.randint(0, SCREEN_WIDTH)

        # lightning flash (very brief overlay)
        if self.weather == 'rain' and self.lightning_timer and random.random() < 0.06:
            flash = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            flash.fill((255,255,255,60))
            self.screen.blit(flash, (0,0))

    def draw_hud(self):
        hud_rect = pygame.Rect(10,10,260,92)
        panel = pygame.Surface((hud_rect.width, hud_rect.height), pygame.SRCALPHA)
        panel.fill((12,18,28,180))
        pygame.draw.rect(panel, WHITE, panel.get_rect(), 2, border_radius=10)
        self.screen.blit(panel, (hud_rect.x, hud_rect.y))
        score_surf = self.font.render(f'Score: {self.score}', True, WHITE)
        lives_surf = self.font.render(f'Lives: {self.lives}', True, WHITE)
        level_surf = self.font.render(f'Level: {self.level}', True, WHITE)
        best_surf = self.font.render(f'Best: {self.best_level}', True, WHITE)
        self.screen.blit(score_surf, (22,18))
        self.screen.blit(lives_surf, (22,38))
        self.screen.blit(level_surf, (22,58))
        self.screen.blit(best_surf, (140,58))
        center_x = SCREEN_WIDTH//2
        y = 12
        small = pygame.font.SysFont(None, 18)
        kinds = list(self.active_powers.keys())
        for idx, kind in enumerate(kinds):
            remaining = max(0.0, self.active_powers[kind])
            box_w = 160
            bx = center_x - (len(kinds) * (box_w+8))//2 + idx*(box_w+8)
            rect = pygame.Rect(bx, y, box_w, 28)
            pygame.draw.rect(self.screen, (18,20,28), rect, border_radius=8)
            pygame.draw.rect(self.screen, WHITE, rect, 2, border_radius=8)
            label = small.render(f'{kind}', True, WHITE)
            self.screen.blit(label, (bx+8, y+4))
            pct = remaining / (REVERSE_DURATION if kind=='REVERSE' else POWER_DURATION)
            bar_w = int((box_w-16) * pct)
            bar_rect = pygame.Rect(bx+8, y+18, bar_w, 6)
            pygame.draw.rect(self.screen, GREEN, bar_rect, border_radius=4)

    # UI screens
    def draw_menu(self):
        self.draw_background()
    
    # Title
        title_font = pygame.font.SysFont(None, 72)
        title = title_font.render('BRICK BREAKER', True, (255, 255, 255))
        self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 80))
    
    # Subtitle (Start prompt)
        subtitle_font = pygame.font.SysFont(None, 26)
        subtitle = subtitle_font.render('Press ENTER to Start — Visual Upgrade', True, (190, 210, 255))
        self.screen.blit(subtitle, (SCREEN_WIDTH//2 - subtitle.get_width()//2, 155))
    
    # “Powered by” footer
        credit_font = pygame.font.SysFont("arial", 20)
        credit = credit_font.render('Powered by POTPOT GAMES', True,(0, 255, 255))
        self.screen.blit(credit, (SCREEN_WIDTH//2 - credit.get_width()//2, 185))

        bx = SCREEN_WIDTH//2 - 120
        by = 280
        if not self.menu_buttons:
            self.menu_buttons = [Button((bx,by,240,54),'Start (ENTER)'),
                                 Button((bx,by+80,240,54),'Instructions'),
                                 Button((bx,by+160,240,54),'Settings'),
                                 Button((bx,by+240,240,54),'Exit')]
        pygame.draw.line(self.screen, (60,200,255), (SCREEN_WIDTH//2-200, by-40), (SCREEN_WIDTH//2+200, by-40), 2)
        for b in self.menu_buttons:
            b.draw(self.screen)

    def draw_settings(self):
        self.draw_background()
        big = pygame.font.SysFont(None, 48)
        title = big.render('Settings', True, WHITE)
        self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 80))
        if not self.settings_buttons:
            bx = SCREEN_WIDTH//2 - 140
            by = 220
            self.settings_buttons = [Button((bx,by,280,54), f'Sound: {"On" if self.sound_on else "Off"}'),
                                     Button((bx,by+80,280,54),'Back')]
        self.settings_buttons[0].label = f'Sound: {"On" if self.sound_on else "Off"}'
        for b in self.settings_buttons:
            b.draw(self.screen)

    def draw_instructions(self):
        self.draw_background()
        big = pygame.font.SysFont(None, 38)
        title = big.render('Instructions', True, WHITE)
        self.screen.blit(title, (SCREEN_WIDTH//2 - title.get_width()//2, 40))
        small = pygame.font.SysFont(None, 20)
        lines = [
            'Controls: Left/Right arrows to move the paddle (reversed by Reverse power-up).',
            'Press ENTER or SPACE to launch stuck balls. P to pause. Mouse to press menu buttons.',
            '',
            'Power-ups:',
            'EXPAND — expands paddle temporarily.',
            'MULTI — adds extra balls (total 3).',
            'SLOW — slows balls down temporarily.',
            'LIFE — grants +1 life.',
            'STICKY — balls stick to paddle; press ENTER to launch.',
            'REVERSE — reverses paddle controls for 5 seconds.'
        ]
        y = 120
        for line in lines:
            self.screen.blit(small.render(line, True, WHITE), (120, y))
            y += 28
        back = Button((SCREEN_WIDTH-180, SCREEN_HEIGHT-100, 140, 54), 'Back')
        back.draw(self.screen)
        self.instr_back = back

    def draw_popup(self, message, labels):
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((6,6,12,180))
        self.screen.blit(overlay, (0,0))
        w,h = 640, 320
        x = (SCREEN_WIDTH-w)//2
        y = (SCREEN_HEIGHT-h)//2
        box = pygame.Rect(x,y,w,h)
        pygame.draw.rect(self.screen, (22,28,40), box, border_radius=14)
        pygame.draw.rect(self.screen, WHITE, box, 3, border_radius=14)
        big = pygame.font.SysFont(None, 32)
        lines = message.split('\n')

        for i, line in enumerate(lines):
            txt = big.render(line, True, WHITE)
            self.screen.blit(txt, (x+30, y+30 + i*38))

        # optional popup_sub (used for max level best display)
        if hasattr(self, 'popup_sub'):
            sub_font = pygame.font.SysFont(None, 24)
            sub_txt = sub_font.render(self.popup_sub, True, GREY)
            self.screen.blit(sub_txt, (x+30, y+30 + (len(lines))*38 + 6))

        self.popup_buttons = []
        btn_w = 160
        btn_h = 54
        spacing = 20
        total_w = len(labels)*btn_w + (len(labels)-1)*spacing
        start_x = x + (w - total_w)//2
        by = y + h - 100
        for i, lab in enumerate(labels):
            rect = (start_x + i*(btn_w+spacing), by, btn_w, btn_h)
            btn = Button(rect, lab)
            btn.draw(self.screen)
            self.popup_buttons.append(btn)

    def draw_game(self):
        self.draw_background()
        for brick in self.bricks:
            brick.draw(self.screen)
        self.paddle.draw(self.screen)
        for b in self.balls:
            b.draw(self.screen)
        for p in self.powerups:
            p.draw(self.screen)
        self.draw_hud()

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / (1000.0 / FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if self.state == 'menu':
                        if event.key == pygame.K_RETURN:
                            self.state = 'playing'
                            self.reset_level(first=True)
                        elif event.key == pygame.K_i:
                            self.state = 'instructions'
                        elif event.key == pygame.K_s:
                            self.state = 'settings'
                    elif self.state == 'settings':
                        if event.key == pygame.K_ESCAPE:
                            self.state = 'menu'
                    elif self.state == 'instructions':
                        if event.key == pygame.K_ESCAPE:
                            self.state = 'menu'
                    elif self.state == 'playing':
                        if event.key in (pygame.K_SPACE, pygame.K_RETURN):
                            for b in self.balls:
                                if b.stuck:
                                    b.stuck = False
                                    b.vx = random.choice([-BASE_SPEED, -BASE_SPEED+1, BASE_SPEED-1, BASE_SPEED])
                                    b.vy = -abs(BASE_SPEED)
                        if event.key == pygame.K_p:
                            self.state = 'paused'
                    elif self.state == 'paused':
                        if event.key == pygame.K_p:
                            self.state = 'playing'
                    elif self.state in ('level_popup','max_popup'):
                        if event.key == pygame.K_n and self.state == 'level_popup':
                            if self.level < MAX_LEVEL:
                                self.level += 1
                                self.reset_level()
                                self.state = 'playing'
                        if event.key == pygame.K_r and self.state == 'max_popup':
                            self.restart_game()
                    elif self.state == 'game_over':
                        if event.key == pygame.K_r:
                            self.restart_game()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mx,my = event.pos
                    if self.state == 'menu':
                        for b in self.menu_buttons:
                            if b.clicked((mx,my)):
                                lab = b.label
                                if lab.startswith('Start'):
                                    self.state = 'playing'
                                    self.reset_level(first=True)
                                elif lab == 'Instructions':
                                    self.state = 'instructions'
                                elif lab == 'Settings':
                                    self.state = 'settings'
                                elif lab == 'Exit':
                                    self.running = False
                    elif self.state == 'settings':
                        for b in self.settings_buttons:
                            if b.clicked((mx,my)):
                                if b.label.startswith('Sound'):
                                    self.sound_on = not self.sound_on
                                elif b.label == 'Back':
                                    self.state = 'menu'
                    elif self.state == 'instructions':
                        if hasattr(self, 'instr_back') and self.instr_back.clicked((mx,my)):
                            self.state = 'menu'
                    elif self.state == 'playing':
                        pass
                    elif self.state == 'paused':
                        self.state = 'playing'
                    elif self.state in ('level_popup','max_popup'):
                        for b in self.popup_buttons:
                            if b.clicked((mx,my)):
                                lab = b.label
                                if lab == 'Next':
                                    if self.level < MAX_LEVEL:
                                        self.level += 1
                                    self.reset_level()
                                    self.state = 'playing'
                                elif lab == 'Previous':
                                    if self.level > 1:
                                        self.level -= 1
                                    self.reset_level()
                                    self.state = 'playing'
                                elif lab == 'Exit':
                                    self.running = False
                                elif lab in ('Restart Game','Play Again'):
                                    self.restart_game()
                                    self.state = 'playing'
                    elif self.state == 'game_over':
                        for b in self.popup_buttons:
                            if b.clicked((mx,my)):
                                if b.label == 'Play Again':
                                    self.restart_game()
                                elif b.label == 'Exit':
                                    self.running = False

            if self.state == 'playing':
                self.update(dt)
            if self.state == 'menu':
                self.draw_menu()
            elif self.state == 'settings':
                self.draw_settings()
            elif self.state == 'instructions':
                self.draw_instructions()
            elif self.state == 'playing':
                self.draw_game()
            elif self.state == 'paused':
                self.draw_game()
                self.draw_popup('Paused', ['Resume','Exit'])
            elif self.state == 'level_popup':
                self.draw_game()
                self.draw_popup(self.popup_message, ['Previous','Next','Exit'])
            elif self.state == 'max_popup':
                self.draw_game()
                # ensure popup_sub exists
                if not hasattr(self, 'popup_sub'):
                    self.popup_sub = f"Best Level: {self.best_level}"
                self.draw_popup(self.popup_message, ['Restart Game','Exit'])
            elif self.state == 'game_over':
                self.draw_game()
                self.draw_popup('Game Over', ['Play Again','Exit'])

            pygame.display.flip()

        pygame.quit()

if __name__ == '__main__':
    Game().run()
