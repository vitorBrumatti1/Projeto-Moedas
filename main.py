import datetime
import math
import random
from pathlib import Path

import arcade
from peewee import Model, SqliteDatabase, CharField, IntegerField, FloatField, DateTimeField
from PIL import Image

LARGURA, ALTURA = 800, 600
TITULO = 'Coletor de Tesouros'
VELOCIDADE_JOGADOR = 4
QUANTIDADE_MOEDAS = 25
PONTOS_MOEDA_ESPECIAL = 5
PONTUACAO_MAXIMA = QUANTIDADE_MOEDAS + PONTOS_MOEDA_ESPECIAL
GRAVIDADE, FORCA_PULO = 0.5, 15
ARQUIVO_SPRITESHEET = 'personagem-spritesheet.png'
LARGURA_FRAME, ALTURA_FRAME, COLUNAS_SPRITESHEET, TOTAL_FRAMES = 96, 128, 10, 10
TEMPO_POR_FRAME = 0.1
DURACAO_FLASH_VERMELHO = 0.55
BASE = Path(__file__).resolve().parent
banco = SqliteDatabase(str(BASE / 'ranking.db'))


def asset(nome):
    return str(BASE / nome)


class BaseModel(Model):
    class Meta:
        database = banco


class Pontuacao(BaseModel):
    nome_jogador = CharField()
    pontos = IntegerField()
    tempo_partida = FloatField()
    data_hora = DateTimeField(default=datetime.datetime.now)

    def __str__(self):
        return f'{self.nome_jogador} - {self.pontos} pts ({self.tempo_partida:.1f}s)'


def inicializar_banco():
    banco.connect(reuse_if_open=True)
    banco.create_tables([Pontuacao], safe=True)


def texto_central(mensagem, altura, tamanho=18, cor=arcade.color.WHITE):
    arcade.draw_text(mensagem, LARGURA / 2, altura, cor, tamanho, anchor_x='center')


def fundo_cobertura(textura):
    arcade.draw_texture_rect(textura, arcade.LBWH(0, 0, LARGURA, ALTURA))


def garantir_spritesheet_jogador():
    caminho = BASE / ARQUIVO_SPRITESHEET
    if caminho.exists():
        return
    pasta = ':resources:images/animated_characters/male_adventurer/maleAdventurer'
    nomes = [f'{pasta}_idle.png', f'{pasta}_jump.png'] + [f'{pasta}_walk{i}.png' for i in range(8)]
    folha = Image.new('RGBA', (LARGURA_FRAME * TOTAL_FRAMES, ALTURA_FRAME), (0, 0, 0, 0))
    for indice, nome in enumerate(nomes):
        imagem = arcade.load_texture(nome).image.copy()
        folha.paste(imagem, (indice * LARGURA_FRAME, 0), imagem)
    folha.save(caminho)


class Jogador(arcade.Sprite):
    DIREITA, ESQUERDA = 1, -1

    def __init__(self):
        garantir_spritesheet_jogador()
        folha = arcade.load_spritesheet(asset(ARQUIVO_SPRITESHEET))
        quadros = folha.get_texture_grid(size=(LARGURA_FRAME, ALTURA_FRAME), columns=COLUNAS_SPRITESHEET, count=TOTAL_FRAMES)
        self.textura_idle_direita = quadros[0]
        self.textura_pulo_direita = quadros[1]
        self.texturas_andando_direita = quadros[2:10]
        self.textura_idle_esquerda = quadros[0].flip_left_right()
        self.textura_pulo_esquerda = quadros[1].flip_left_right()
        self.texturas_andando_esquerda = [t.flip_left_right() for t in self.texturas_andando_direita]
        super().__init__(self.textura_idle_direita, scale=0.55)
        self.virado_para = self.DIREITA
        self.frame_atual = 0
        self.tempo_animacao = 0.0
        self.tempo_piscando = 0.0
        self.tempo_total = 0.0

    def receber_dano(self):
        self.tempo_piscando = 0.9

    def update(self, delta_time=1 / 60):
        self.tempo_total += delta_time
        self.tempo_piscando = max(0.0, self.tempo_piscando - delta_time)
        self.alpha = 90 if self.tempo_piscando > 0 and int(self.tempo_total * 12) % 2 else 255
        if self.change_x > 0:
            self.virado_para = self.DIREITA
        elif self.change_x < 0:
            self.virado_para = self.ESQUERDA
        direita = self.virado_para == self.DIREITA
        if abs(self.change_y) > 0.01:
            self.texture = self.textura_pulo_direita if direita else self.textura_pulo_esquerda
            self.tempo_animacao = 0.0
            return
        if self.change_x == 0:
            self.frame_atual = 0
            self.tempo_animacao = 0.0
            self.texture = self.textura_idle_direita if direita else self.textura_idle_esquerda
            return
        self.tempo_animacao += delta_time
        while self.tempo_animacao >= TEMPO_POR_FRAME:
            self.tempo_animacao -= TEMPO_POR_FRAME
            self.frame_atual = (self.frame_atual + 1) % len(self.texturas_andando_direita)
        ciclo = self.texturas_andando_direita if direita else self.texturas_andando_esquerda
        self.texture = ciclo[self.frame_atual]


class Moeda(arcade.Sprite):
    def __init__(self):
        super().__init__(asset('moeda.png'), scale=0.08)


class MoedaEspecial(arcade.Sprite):
    def __init__(self):
        super().__init__(asset('moeda.png'), scale=0.12)

    def update(self, delta_time=1 / 60):
        self.center_x += self.change_x
        self.center_y += self.change_y
        if self.left < 0:
            self.left, self.change_x = 0, abs(self.change_x)
        elif self.right > LARGURA:
            self.right, self.change_x = LARGURA, -abs(self.change_x)
        if self.bottom < 0:
            self.bottom, self.change_y = 0, abs(self.change_y)
        elif self.top > ALTURA:
            self.top, self.change_y = ALTURA, -abs(self.change_y)


class Bloco(arcade.Sprite):
    def __init__(self):
        super().__init__(asset('plataforma.png'), scale=0.5)


class InimigoPlataforma(arcade.Sprite):
    def __init__(self, plataforma, velocidade=2):
        super().__init__(asset('inimigoDireita.png'), scale=0.05)
        self.direita = arcade.load_texture(asset('inimigoDireita.png'))
        self.esquerda = arcade.load_texture(asset('inimigoEsquerda.png'))
        self.change_x = velocidade
        self.limite_esquerda = plataforma.left
        self.limite_direita = plataforma.right
        self.center_x = plataforma.center_x
        self.center_y = plataforma.top + self.height / 2

    def update(self, delta_time=1 / 60):
        self.center_x += self.change_x
        if self.left <= self.limite_esquerda:
            self.left = self.limite_esquerda
            self.change_x = abs(self.change_x)
        elif self.right >= self.limite_direita:
            self.right = self.limite_direita
            self.change_x = -abs(self.change_x)
        self.texture = self.direita if self.change_x > 0 else self.esquerda


class InimigoEspecial(arcade.Sprite):
    def __init__(self, jogador):
        super().__init__(asset('espinho.png'), scale=0.08)
        self.jogador = jogador
        self.velocidade = 1.2

    def update(self, delta_time=1 / 60):
        if abs(self.center_x - self.jogador.center_x) > self.velocidade:
            self.center_x += self.velocidade if self.center_x < self.jogador.center_x else -self.velocidade
        if abs(self.center_y - self.jogador.center_y) > self.velocidade:
            self.center_y += self.velocidade if self.center_y < self.jogador.center_y else -self.velocidade


class Particula:
    def __init__(self, x, y, cor):
        angulo = random.uniform(0, 2 * math.pi)
        velocidade = random.uniform(70, 190)
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(angulo) * velocidade, math.sin(angulo) * velocidade
        self.vida = random.uniform(0.3, 0.65)
        self.max_vida = self.vida
        self.raio = random.uniform(2.5, 5)
        self.cor = cor

    def update(self, dt):
        self.vida -= dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy -= 220 * dt

    def draw(self):
        if self.vida > 0:
            alpha = int(255 * max(0, self.vida / self.max_vida))
            arcade.draw_circle_filled(self.x, self.y, self.raio, (*self.cor, alpha))


class TextoFlutuante:
    def __init__(self, mensagem, x, y, cor):
        self.mensagem, self.x, self.y, self.cor = mensagem, x, y, cor
        self.vida, self.max_vida = 0.85, 0.85

    def update(self, dt):
        self.y += 55 * dt
        self.vida -= dt

    def draw(self):
        if self.vida > 0:
            alpha = int(255 * self.vida / self.max_vida)
            arcade.draw_text(self.mensagem, self.x, self.y, (*self.cor, alpha), 17, bold=True, anchor_x='center')


class TelaMenu(arcade.View):
    def __init__(self):
        super().__init__()
        self.fundo = arcade.load_texture(asset('fundoMenu.png'))

    def on_draw(self):
        self.clear()
        fundo_cobertura(self.fundo)
        texto_central('COLETOR DE TESOUROS', 450, 32, arcade.color.YELLOW)
        for i, opcao in enumerate(['[J] Jogar', '[R] Ranking', '[I] Instruções', '[S] Sobre o jogo', '[ESC] Sair']):
            texto_central(opcao, 345 - i * 42)

    def on_key_press(self, key, modifiers):
        if key == arcade.key.J:
            self.window.show_view(TelaJogo())
        elif key == arcade.key.R:
            self.window.show_view(TelaRanking())
        elif key == arcade.key.I:
            self.window.show_view(TelaInstrucoes())
        elif key == arcade.key.S:
            self.window.show_view(TelaSobre())
        elif key == arcade.key.ESCAPE:
            arcade.close_window()


class TelaInstrucoes(arcade.View):
    def __init__(self):
        super().__init__()
        self.fundo = arcade.load_texture(asset('fundoMenu.png'))

    def on_draw(self):
        self.clear()
        fundo_cobertura(self.fundo)
        texto_central('INSTRUÇÕES', 530, 30)
        linhas = ['Colete todas as moedas para terminar o jogo.', 'Cada moeda normal vale 1 ponto.',
                  'A moeda especial rebate nas paredes e vale 5 pontos.', 'Os inimigos normais patrulham plataformas e tiram 1 ponto.',
                  'O inimigo especial persegue o jogador.', 'Movimento: A/D ou setas esquerda/direita.',
                  'Pulo: ESPAÇO, W ou seta para cima.', 'Impactos provocam tremor, partículas e invulnerabilidade.']
        for i, linha in enumerate(linhas):
            arcade.draw_text(linha, 45, 458 - i * 42, arcade.color.WHITE, 15)
        texto_central('[M] ou [ESC] Voltar ao menu', 65, 16, arcade.color.LIGHT_GRAY)

    def on_key_press(self, key, modifiers):
        if key in (arcade.key.M, arcade.key.ESCAPE):
            self.window.show_view(TelaMenu())


class TelaSobre(arcade.View):
    def __init__(self):
        super().__init__()
        self.fundo = arcade.load_texture(asset('fundoMenu.png'))
        self.avatares = arcade.SpriteList()
        avatar = arcade.Sprite(asset('personagem-direita.png'), scale=0.08)
        avatar.position = (LARGURA / 2, 270)
        self.avatares.append(avatar)

    def on_draw(self):
        self.clear()
        fundo_cobertura(self.fundo)
        texto_central('SOBRE O JOGO', 500, 30)
        texto_central('Desenvolvido por:', 420)
        texto_central('Vitor Rufino Brumatti - 3º Info', 375, 20, arcade.color.YELLOW)
        self.avatares.draw()
        texto_central('[M] ou [ESC] Voltar ao menu', 100, 16, arcade.color.LIGHT_GRAY)

    def on_key_press(self, key, modifiers):
        if key in (arcade.key.M, arcade.key.ESCAPE):
            self.window.show_view(TelaMenu())


class TelaRanking(arcade.View):
    def __init__(self):
        super().__init__()
        self.fundo = arcade.load_texture(asset('fundoMenu.png'))
        self.melhores = list(Pontuacao.select().order_by(Pontuacao.pontos.desc(), Pontuacao.tempo_partida.asc()).limit(10))

    def on_draw(self):
        self.clear()
        fundo_cobertura(self.fundo)
        texto_central('TOP 10 - RANKING', 535, 30, arcade.color.GOLD)
        for rotulo, x in [('Pos.', 100), ('Jogador', 170), ('Pontos', 470), ('Tempo', 590)]:
            arcade.draw_text(rotulo, x, 485, arcade.color.LIGHT_GRAY, 15)
        if not self.melhores:
            texto_central('Ainda não há pontuações registradas.', 320, 18, arcade.color.LIGHT_GRAY)
        for indice, registro in enumerate(self.melhores):
            y = 445 - indice * 34
            arcade.draw_text(f'{indice + 1}º', 105, y, arcade.color.WHITE, 15)
            arcade.draw_text(registro.nome_jogador[:20], 170, y, arcade.color.WHITE, 15)
            arcade.draw_text(str(registro.pontos), 485, y, arcade.color.YELLOW, 15)
            arcade.draw_text(f'{registro.tempo_partida:.1f}s', 590, y, arcade.color.WHITE, 15)
        texto_central('[J] Jogar   |   [M] ou [ESC] Menu', 55, 15, arcade.color.LIGHT_GRAY)

    def on_key_press(self, key, modifiers):
        if key == arcade.key.J:
            self.window.show_view(TelaJogo())
        elif key in (arcade.key.M, arcade.key.ESCAPE):
            self.window.show_view(TelaMenu())


class TelaJogo(arcade.View):
    def __init__(self):
        super().__init__()
        self.pontos, self.tempo = 0, 0.0
        self.tempo_alerta, self.tempo_sem_novo_dano = 0.0, 0.0
        self.flash_vermelho_tempo = 0.0
        self.particulas = []
        self.textos_flutuantes = []
        self.tremor_tempo, self.tremor_duracao, self.tremor_intensidade = 0.0, 0.0, 0.0
        self.teclas_esquerda, self.teclas_direita = set(), set()
        self.fundo = arcade.load_texture(asset('fundo.png'))
        self.lista_jogador, self.lista_moedas = arcade.SpriteList(), arcade.SpriteList()
        self.lista_inimigos, self.lista_inimigo_especial = arcade.SpriteList(), arcade.SpriteList()
        self.lista_blocos = arcade.SpriteList()
        self.jogador = Jogador()
        self.jogador.position = (100, 100)
        self.lista_jogador.append(self.jogador)
        self.criar_chao()
        self.plataformas_suspensas = []
        for x, y in [(170, 170), (400, 250), (650, 180), (260, 380), (560, 400)]:
            bloco = Bloco()
            bloco.position = (x, y)
            self.lista_blocos.append(bloco)
            self.plataformas_suspensas.append(bloco)
        self.physics_engine = arcade.PhysicsEnginePlatformer(self.jogador, walls=self.lista_blocos, gravity_constant=GRAVIDADE)
        for _ in range(QUANTIDADE_MOEDAS):
            moeda = Moeda()
            self.posicionar_sem_colisao(moeda, self.lista_moedas)
            self.lista_moedas.append(moeda)
        self.moeda_especial = MoedaEspecial()
        self.posicionar_sem_colisao(self.moeda_especial, self.lista_moedas)
        self.moeda_especial.change_x, self.moeda_especial.change_y = 3, 3
        self.lista_moedas.append(self.moeda_especial)
        for plataforma, velocidade in [(self.plataformas_suspensas[0], 1), (self.plataformas_suspensas[2], 1.5)]:
            self.lista_inimigos.append(InimigoPlataforma(plataforma, velocidade))
        self.inimigo_especial = InimigoEspecial(self.jogador)
        self.posicionar_sem_colisao(self.inimigo_especial, self.lista_moedas)
        self.lista_inimigo_especial.append(self.inimigo_especial)
        self.camera = arcade.Camera2D()

    def criar_chao(self):
        x = 0
        while x < LARGURA:
            bloco = Bloco()
            bloco.left, bloco.bottom = x, 0
            self.lista_blocos.append(bloco)
            x = bloco.right

    def posicionar_sem_colisao(self, sprite, lista_existente):
        for _ in range(150):
            sprite.center_x = random.randint(50, LARGURA - 50)
            sprite.center_y = random.randint(70, ALTURA - 50)
            if not arcade.check_for_collision(sprite, self.jogador) and not arcade.check_for_collision_with_list(sprite, lista_existente) and not arcade.check_for_collision_with_list(sprite, self.lista_blocos):
                return

    def soltar_particulas(self, x, y, cor, quantidade):
        self.particulas.extend(Particula(x, y, cor) for _ in range(quantidade))

    def iniciar_tremor(self, intensidade=7, duracao=0.22):
        self.tremor_intensidade = max(self.tremor_intensidade, intensidade)
        self.tremor_tempo = duracao
        self.tremor_duracao = duracao

    def causar_dano(self, x, y):
        if self.tempo_sem_novo_dano > 0:
            return False
        self.pontos -= 1
        self.tempo_sem_novo_dano = 1.0
        self.tempo_alerta = 0.7
        self.flash_vermelho_tempo = DURACAO_FLASH_VERMELHO
        self.jogador.receber_dano()
        self.soltar_particulas(self.jogador.center_x, self.jogador.center_y, (255, 75, 75), 18)
        self.textos_flutuantes.append(TextoFlutuante('-1', self.jogador.center_x, self.jogador.top + 15, (255, 80, 80)))
        self.iniciar_tremor(9, 0.27)
        return True

    def on_draw(self):
        self.clear()
        if self.tremor_tempo > 0:
            fator = self.tremor_tempo / max(self.tremor_duracao, 0.001)
            desloc_x = random.uniform(-1, 1) * self.tremor_intensidade * fator
            desloc_y = random.uniform(-1, 1) * self.tremor_intensidade * fator
        else:
            desloc_x = desloc_y = 0
        self.camera.position = (LARGURA / 2 + desloc_x, ALTURA / 2 + desloc_y)
        self.camera.use()
        fundo_cobertura(self.fundo)
        self.lista_blocos.draw()
        self.lista_moedas.draw()
        self.lista_inimigos.draw()
        self.lista_inimigo_especial.draw()
        self.lista_jogador.draw()
        for particula in self.particulas:
            particula.draw()
        for texto in self.textos_flutuantes:
            texto.draw()
        self.camera.position = (LARGURA / 2, ALTURA / 2)
        self.camera.use()
        arcade.draw_text(f'Pontos: {self.pontos}', 15, 570, arcade.color.WHITE, 16)
        arcade.draw_text(f'Tempo: {self.tempo:.1f} segundos', 15, 545, arcade.color.WHITE, 14)
        if self.tempo_alerta > 0:
            texto_central('DANO RECEBIDO! -1 PONTO', 510, 20, arcade.color.RED)

        if self.flash_vermelho_tempo > 0:
            progresso = 1.0 - self.flash_vermelho_tempo / DURACAO_FLASH_VERMELHO
            pulso = max(0.0, math.cos(4.0 * math.pi * progresso)) ** 2
            intensidade = int(190 * (1.0 - progresso) * pulso)
            if intensidade > 0:
                arcade.draw_rect_filled(
                    arcade.LBWH(0, 0, LARGURA, ALTURA),
                    (255, 20, 30, intensidade),
                )

    def on_update(self, delta_time):
        self.tempo += delta_time
        self.tempo_alerta = max(0.0, self.tempo_alerta - delta_time)
        self.flash_vermelho_tempo = max(0.0, self.flash_vermelho_tempo - delta_time)
        self.tempo_sem_novo_dano = max(0.0, self.tempo_sem_novo_dano - delta_time)
        self.tremor_tempo = max(0.0, self.tremor_tempo - delta_time)
        for particula in self.particulas:
            particula.update(delta_time)
        self.particulas = [p for p in self.particulas if p.vida > 0]
        for texto in self.textos_flutuantes:
            texto.update(delta_time)
        self.textos_flutuantes = [t for t in self.textos_flutuantes if t.vida > 0]
        self.lista_moedas.update(delta_time)
        self.lista_inimigos.update(delta_time)
        self.lista_inimigo_especial.update(delta_time)
        self.physics_engine.update()
        self.jogador.update(delta_time)
        if self.jogador.left < 0:
            self.jogador.left = 0
        if self.jogador.right > LARGURA:
            self.jogador.right = LARGURA
        for moeda in arcade.check_for_collision_with_list(self.jogador, self.lista_moedas):
            especial = isinstance(moeda, MoedaEspecial)
            ganho = PONTOS_MOEDA_ESPECIAL if especial else 1
            self.pontos += ganho
            self.soltar_particulas(moeda.center_x, moeda.center_y, (255, 220, 35), 20 if especial else 10)
            self.textos_flutuantes.append(TextoFlutuante(f'+{ganho}', moeda.center_x, moeda.center_y + 18, (255, 231, 65)))
            if especial:
                self.iniciar_tremor(3, 0.12)
            moeda.remove_from_sprite_lists()
        if arcade.check_for_collision_with_list(self.jogador, self.lista_inimigos):
            self.causar_dano(self.jogador.center_x, self.jogador.center_y)
        if arcade.check_for_collision_with_list(self.jogador, self.lista_inimigo_especial):
            if self.causar_dano(self.inimigo_especial.center_x, self.inimigo_especial.center_y):
                self.posicionar_sem_colisao(self.inimigo_especial, self.lista_moedas)
        if len(self.lista_moedas) == 0:
            self.window.show_view(TelaGameOver(self.pontos, self.tempo))

    def atualizar_movimento(self):
        esquerda, direita = bool(self.teclas_esquerda), bool(self.teclas_direita)
        self.jogador.change_x = (int(direita) - int(esquerda)) * VELOCIDADE_JOGADOR

    def on_key_press(self, key, modifiers):
        if key in (arcade.key.LEFT, arcade.key.A):
            self.teclas_esquerda.add(key)
            self.atualizar_movimento()
        elif key in (arcade.key.RIGHT, arcade.key.D):
            self.teclas_direita.add(key)
            self.atualizar_movimento()
        elif key in (arcade.key.SPACE, arcade.key.UP, arcade.key.W):
            if self.physics_engine.can_jump():
                self.jogador.change_y = FORCA_PULO
        elif key == arcade.key.ESCAPE:
            self.window.show_view(TelaMenu())

    def on_key_release(self, key, modifiers):
        self.teclas_esquerda.discard(key)
        self.teclas_direita.discard(key)
        self.atualizar_movimento()


class TelaGameOver(arcade.View):
    def __init__(self, pontos, tempo):
        super().__init__()
        self.pontos, self.tempo = pontos, tempo
        self.nome_jogador, self.salvo = '', False
        self.mensagem = 'Digite seu nome e pressione ENTER para salvar.'

    def on_draw(self):
        self.clear()
        if self.pontos == PONTUACAO_MAXIMA:
            texto_central('VITÓRIA PERFEITA!', 500, 32, arcade.color.GOLD)
        else:
            texto_central('PARABÉNS! JOGO CONCLUÍDO', 500, 28, arcade.color.YELLOW)
        texto_central(f'Pontuação final: {self.pontos}', 410, 20)
        texto_central(f'Tempo total: {self.tempo:.1f} segundos', 375, 18)
        if not self.salvo:
            texto_central('NOME DO JOGADOR:', 300, 16, arcade.color.LIGHT_GRAY)
            texto_central(self.nome_jogador or '_', 255, 24)
            texto_central(self.mensagem, 205, 15, arcade.color.LIGHT_GRAY)
        else:
            texto_central('Pontuação salva no ranking!', 285, 20, arcade.color.GREEN_YELLOW)
            texto_central('[R] Ranking   |   [J] Jogar novamente   |   [M] Menu', 190, 15, arcade.color.LIGHT_GRAY)

    def on_text(self, texto):
        if not self.salvo and texto.isprintable():
            self.nome_jogador += texto[:max(0, 20 - len(self.nome_jogador))]

    def on_key_press(self, key, modifiers):
        if not self.salvo:
            if key == arcade.key.BACKSPACE:
                self.nome_jogador = self.nome_jogador[:-1]
            elif key in (arcade.key.ENTER, arcade.key.RETURN):
                nome = self.nome_jogador.strip()
                if not nome:
                    self.mensagem = 'Digite pelo menos 1 caractere antes de salvar.'
                    return
                Pontuacao.create(nome_jogador=nome, pontos=self.pontos, tempo_partida=self.tempo)
                self.salvo = True
            return
        if key == arcade.key.R:
            self.window.show_view(TelaRanking())
        elif key == arcade.key.J:
            self.window.show_view(TelaJogo())
        elif key == arcade.key.M:
            self.window.show_view(TelaMenu())
        elif key == arcade.key.ESCAPE:
            arcade.close_window()


def main():
    inicializar_banco()
    janela = arcade.Window(LARGURA, ALTURA, TITULO)
    janela.show_view(TelaMenu())
    arcade.run()


if __name__ == '__main__':
    main()
