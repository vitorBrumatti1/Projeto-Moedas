import datetime
from pathlib import Path

import arcade
import random
from peewee import (
    Model,
    SqliteDatabase,
    CharField,
    IntegerField,
    FloatField,
    DateTimeField,
)
from PIL import Image

LARGURA = 800
ALTURA = 600
TITULO = "Coletor de Tesouros"

VELOCIDADE_JOGADOR = 4
QUANTIDADE_MOEDAS = 25
PONTOS_MOEDA_ESPECIAL = 5
GRAVIDADE = 0.5
FORCA_PULO = 15
PONTUACAO_MAXIMA = QUANTIDADE_MOEDAS + PONTOS_MOEDA_ESPECIAL

ARQUIVO_SPRITESHEET = "personagem-spritesheet2.png"
LARGURA_FRAME = 96
ALTURA_FRAME = 128
COLUNAS_SPRITESHEET = 10
TOTAL_FRAMES = 10
TEMPO_POR_FRAME = 0.1


banco = SqliteDatabase("ranking.db")


class BaseModel(Model):
    class Meta:
        database = banco

class Pontuacao(BaseModel):
    nome_jogador = CharField()
    pontos = IntegerField()
    tempo_partida = FloatField()
    data_hora = DateTimeField(default=datetime.datetime.now)

    def __str__(self):
        return f"{self.nome_jogador} - {self.pontos} pts ({self.tempo_partida:.1f}s)"

def inicializar_banco():
    banco.connect(reuse_if_open=True)
    banco.create_tables([Pontuacao])


def desenhar_texto_central(texto, altura, tamanho=18, cor=arcade.color.WHITE):
    arcade.draw_text(
        texto,
        LARGURA / 2,
        altura,
        cor,
        tamanho,
        anchor_x="center",
    )


def garantir_spritesheet_jogador():
    caminho = Path(ARQUIVO_SPRITESHEET)
    if caminho.exists():
        return

    base = ":resources:images/animated_characters/male_adventurer/maleAdventurer"
    arquivos = [
        f"{base}_idle.png",
        f"{base}_jump.png",
        *[f"{base}_walk{i}.png" for i in range(8)],
    ]

    folha = Image.new(
        "RGBA",
        (LARGURA_FRAME * TOTAL_FRAMES, ALTURA_FRAME),
        (0, 0, 0, 0),
    )

    for indice, arquivo in enumerate(arquivos):
        textura = arcade.load_texture(arquivo)
        imagem = textura.image.copy()
        folha.paste(imagem, (indice * LARGURA_FRAME, 0), imagem)

    folha.save(caminho)


class Jogador(arcade.Sprite):
    DIREITA = 1
    ESQUERDA = -1

    def __init__(self):
        garantir_spritesheet_jogador()

        folha = arcade.load_spritesheet(ARQUIVO_SPRITESHEET)
        quadros = folha.get_texture_grid(
            size=(LARGURA_FRAME, ALTURA_FRAME),
            columns=COLUNAS_SPRITESHEET,
            count=TOTAL_FRAMES,
        )

        self.textura_idle_direita = quadros[0]
        self.textura_pulo_direita = quadros[1]
        self.texturas_andando_direita = quadros[2:10]

        self.textura_idle_esquerda = self.textura_idle_direita.flip_left_right()
        self.textura_pulo_esquerda = self.textura_pulo_direita.flip_left_right()
        self.texturas_andando_esquerda = [
            textura.flip_left_right()
            for textura in self.texturas_andando_direita
        ]

        super().__init__(self.textura_idle_direita, scale=0.55)

        self.virado_para = self.DIREITA
        self.frame_atual = 0
        self.tempo_animacao = 0.0

    def update(self, delta_time=1 / 60):
        if self.change_x > 0:
            self.virado_para = self.DIREITA
        elif self.change_x < 0:
            self.virado_para = self.ESQUERDA

        if self.change_y != 0:
            if self.virado_para == self.DIREITA:
                self.texture = self.textura_pulo_direita
            else:
                self.texture = self.textura_pulo_esquerda
            return

        if self.change_x == 0:
            self.frame_atual = 0
            self.tempo_animacao = 0.0

            if self.virado_para == self.DIREITA:
                self.texture = self.textura_idle_direita
            else:
                self.texture = self.textura_idle_esquerda
            return

        self.tempo_animacao += delta_time

        if self.tempo_animacao >= TEMPO_POR_FRAME:
            self.tempo_animacao -= TEMPO_POR_FRAME
            self.frame_atual = (self.frame_atual + 1) % len(self.texturas_andando_direita)

        if self.virado_para == self.DIREITA:
            self.texture = self.texturas_andando_direita[self.frame_atual]
        else:
            self.texture = self.texturas_andando_esquerda[self.frame_atual]

        if self.left < 0:
            self.left = 0
        if self.right > LARGURA:
            self.right = LARGURA


class Moeda(arcade.Sprite):
    def __init__(self):
        super().__init__("moeda.png", scale=0.08)


class Bloco(arcade.Sprite):

    def __init__(self):
        super().__init__("plataforma.png", scale=0.5)


class MoedaEspecial(arcade.Sprite):
    def __init__(self):
        super().__init__("moeda.png", scale=0.12)

    def update(self, delta_time=1 / 60):
        self.center_x += self.change_x
        self.center_y += self.change_y

        if self.left < 0:
            self.left = 0
            self.change_x *= -1
        elif self.right > LARGURA:
            self.right = LARGURA
            self.change_x *= -1

        if self.bottom < 0:
            self.bottom = 0
            self.change_y *= -1
        elif self.top > ALTURA:
            self.top = ALTURA
            self.change_y *= -1


class InimigoPlataforma(arcade.Sprite):
    def __init__(self, plataforma, velocidade=2):
        super().__init__("inimigoDireita.png", scale=0.05)

        self.textura_direita = arcade.load_texture("inimigoDireita.png")
        self.textura_esquerda = arcade.load_texture("inimigoEsquerda.png")
        self.change_x = velocidade

        self.limite_esquerda = plataforma.left
        self.limite_direita = plataforma.right

        self.center_x = plataforma.center_x
        self.center_y = plataforma.top + self.height / 2

    def update(self, delta_time=1 / 60):
        self.center_x += self.change_x

        if self.change_x > 0:
            self.texture = self.textura_direita
        elif self.change_x < 0:
            self.texture = self.textura_esquerda

        if self.left <= self.limite_esquerda:
            self.left = self.limite_esquerda
            self.change_x = abs(self.change_x)
            self.texture = self.textura_direita
        elif self.right >= self.limite_direita:
            self.right = self.limite_direita
            self.change_x = -abs(self.change_x)
            self.texture = self.textura_esquerda


class InimigoEspecial(arcade.Sprite):
    def __init__(self, jogador):
        super().__init__("espinho.png", scale=0.08)
        self.jogador = jogador
        self.velocidade = 1.2

    def update(self, delta_time=1 / 60):
        if self.center_x < self.jogador.center_x:
            self.center_x += self.velocidade
        elif self.center_x > self.jogador.center_x:
            self.center_x -= self.velocidade

        if self.center_y < self.jogador.center_y:
            self.center_y += self.velocidade
        elif self.center_y > self.jogador.center_y:
            self.center_y -= self.velocidade

class TelaMenu(arcade.View):
    def __init__(self):
        super().__init__()
        self.fundo = arcade.load_texture("fundoMenu.png")

    def on_show_view(self):
        arcade.set_background_color(arcade.color.AMAZON)

    def on_draw(self):
        self.clear()

        arcade.draw_texture_rect(
            self.fundo,
            arcade.LBWH(0, 0, LARGURA, ALTURA),
        )

        desenhar_texto_central(
            "COLETOR DE TESOUROS",
            450,
            32,
            arcade.color.YELLOW,
        )

        opcoes = [
            "[J] Jogar",
            "[R] Ranking",
            "[I] Instruções",
            "[S] Sobre o jogo",
            "[ESC] Sair",
        ]

        altura = 345
        for opcao in opcoes:
            desenhar_texto_central(opcao, altura)
            altura -= 42

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
        self.fundo = arcade.load_texture("fundoMenu.png")

    def on_show_view(self):
        arcade.set_background_color(arcade.color.AMAZON)

    def on_draw(self):
        self.clear()

        arcade.draw_texture_rect(
            self.fundo,
            arcade.LBWH(0, 0, LARGURA, ALTURA),
        )

        desenhar_texto_central("INSTRUÇÕES", 530, 30)

        instrucoes = [
            "Colete todas as moedas para terminar o jogo.",
            "Cada moeda normal vale 1 ponto.",
            "A moeda especial rebate nas paredes e vale 5 pontos.",
            "Os inimigos normais patrulham plataformas e tiram 1 ponto.",
            "O inimigo especial persegue o jogador.",
            "Movimento: A/D ou setas esquerda/direita.",
            "Pulo: ESPAÇO, W ou seta para cima.",
        ]

        altura = 455
        for texto in instrucoes:
            arcade.draw_text(
                texto,
                70,
                altura,
                arcade.color.WHITE,
                16,
            )
            altura -= 43

        desenhar_texto_central(
            "[M] ou [ESC] Voltar ao menu",
            90,
            16,
            arcade.color.LIGHT_GRAY,
        )

    def on_key_press(self, key, modifiers):
        if key == arcade.key.M or key == arcade.key.ESCAPE:
            self.window.show_view(TelaMenu())


class TelaSobre(arcade.View):
    def __init__(self):
        super().__init__()
        self.fundo = arcade.load_texture("fundoMenu.png")
        self.lista_avatares = arcade.SpriteList()

        self.avatar = arcade.Sprite("personagem-direita.png", scale=0.08)
        self.avatar.center_x = LARGURA / 2
        self.avatar.center_y = 270
        self.lista_avatares.append(self.avatar)

    def on_show_view(self):
        arcade.set_background_color(arcade.color.AMAZON)

    def on_draw(self):
        self.clear()

        arcade.draw_texture_rect(
            self.fundo,
            arcade.LBWH(0, 0, LARGURA, ALTURA),
        )

        desenhar_texto_central("SOBRE O JOGO", 500, 30)
        desenhar_texto_central("Desenvolvido por:", 420)
        desenhar_texto_central(
            "Vitor Rufino Brumatti - 3º Info",
            375,
            20,
            arcade.color.YELLOW,
        )

        self.lista_avatares.draw()

        desenhar_texto_central(
            "[M] ou [ESC] Voltar ao menu",
            100,
            16,
            arcade.color.LIGHT_GRAY,
        )

    def on_key_press(self, key, modifiers):
        if key == arcade.key.M or key == arcade.key.ESCAPE:
            self.window.show_view(TelaMenu())


class TelaRanking(arcade.View):
    def __init__(self):
        super().__init__()
        self.fundo = arcade.load_texture("fundoMenu.png")

        self.melhores = list(
            Pontuacao.select()
            .order_by(Pontuacao.pontos.desc())
            .limit(10)
        )

    def on_show_view(self):
        arcade.set_background_color(arcade.color.AMAZON)

    def on_draw(self):
        self.clear()

        arcade.draw_texture_rect(
            self.fundo,
            arcade.LBWH(0, 0, LARGURA, ALTURA),
        )

        desenhar_texto_central("TOP 10 - RANKING", 535, 30, arcade.color.GOLD)

        arcade.draw_text("Pos.", 100, 485, arcade.color.LIGHT_GRAY, 15)
        arcade.draw_text("Jogador", 170, 485, arcade.color.LIGHT_GRAY, 15)
        arcade.draw_text("Pontos", 470, 485, arcade.color.LIGHT_GRAY, 15)
        arcade.draw_text("Tempo", 590, 485, arcade.color.LIGHT_GRAY, 15)

        if not self.melhores:
            desenhar_texto_central(
                "Ainda não há pontuações registradas.",
                320,
                18,
                arcade.color.LIGHT_GRAY,
            )
        else:
            for indice, registro in enumerate(self.melhores):
                y = 445 - indice * 34

                arcade.draw_text(
                    f"{indice + 1}º",
                    105,
                    y,
                    arcade.color.WHITE,
                    15,
                )
                arcade.draw_text(
                    registro.nome_jogador,
                    170,
                    y,
                    arcade.color.WHITE,
                    15,
                )
                arcade.draw_text(
                    str(registro.pontos),
                    485,
                    y,
                    arcade.color.YELLOW,
                    15,
                )
                arcade.draw_text(
                    f"{registro.tempo_partida:.1f}s",
                    590,
                    y,
                    arcade.color.WHITE,
                    15,
                )

        desenhar_texto_central(
            "[J] Jogar   |   [M] ou [ESC] Menu",
            55,
            15,
            arcade.color.LIGHT_GRAY,
        )

    def on_key_press(self, key, modifiers):
        if key == arcade.key.J:
            self.window.show_view(TelaJogo())
        elif key == arcade.key.M or key == arcade.key.ESCAPE:
            self.window.show_view(TelaMenu())


class TelaJogo(arcade.View):
    def __init__(self):
        super().__init__()

        self.pontos = 0
        self.tempo = 0.0
        self.alerta_dano = False
        self.tempo_alerta = 0.0
        self.tempo_sem_novo_dano = 0.0

        self.fundo = arcade.load_texture("fundo.png")

        self.lista_jogador = arcade.SpriteList()
        self.lista_moedas = arcade.SpriteList()
        self.lista_inimigos = arcade.SpriteList()
        self.lista_inimigo_especial = arcade.SpriteList()
        self.lista_blocos = arcade.SpriteList()

        self.jogador = Jogador()
        self.jogador.center_x = 100
        self.jogador.center_y = 100
        self.lista_jogador.append(self.jogador)

        self.criar_chao()

        posicoes_plataformas = [
            (170, 170),
            (400, 250),
            (650, 180),
            (260, 350),
            (560, 430),
        ]

        self.plataformas_suspensas = []
        for x, y in posicoes_plataformas:
            bloco = Bloco()
            bloco.center_x = x
            bloco.center_y = y
            self.lista_blocos.append(bloco)
            self.plataformas_suspensas.append(bloco)

        self.physics_engine = arcade.PhysicsEnginePlatformer(
            self.jogador,
            walls=self.lista_blocos,
            gravity_constant=GRAVIDADE,
        )

        for _ in range(QUANTIDADE_MOEDAS):
            moeda = Moeda()
            self.posicionar_sem_colisao(moeda, self.lista_moedas)
            self.lista_moedas.append(moeda)

        self.moeda_especial = MoedaEspecial()
        self.posicionar_sem_colisao(self.moeda_especial, self.lista_moedas)
        self.moeda_especial.change_x = 3
        self.moeda_especial.change_y = 3
        self.lista_moedas.append(self.moeda_especial)

        self.inimigo1 = InimigoPlataforma(
            self.plataformas_suspensas[0],
            velocidade=1,
        )
        self.inimigo2 = InimigoPlataforma(
            self.plataformas_suspensas[2],
            velocidade=1.5,
        )

        self.lista_inimigos.append(self.inimigo1)
        self.lista_inimigos.append(self.inimigo2)

        self.inimigo_especial = InimigoEspecial(self.jogador)
        self.posicionar_sem_colisao(
            self.inimigo_especial,
            self.lista_moedas,
        )
        self.lista_inimigo_especial.append(self.inimigo_especial)

    def criar_chao(self):
        x = 0

        while x < LARGURA:
            bloco = Bloco()
            bloco.left = x
            bloco.bottom = 0
            self.lista_blocos.append(bloco)

            x = bloco.right

    def on_show_view(self):
        arcade.set_background_color(arcade.color.AMAZON)

    def posicionar_sem_colisao(self, sprite, lista_existente):
        for _ in range(100):
            sprite.center_x = random.randint(50, LARGURA - 50)
            sprite.center_y = random.randint(70, ALTURA - 50)

            colidiu_jogador = arcade.check_for_collision(sprite, self.jogador)
            colidiu_lista = arcade.check_for_collision_with_list(
                sprite,
                lista_existente,
            )
            colidiu_blocos = arcade.check_for_collision_with_list(
                sprite,
                self.lista_blocos,
            )

            if (
                not colidiu_jogador
                and len(colidiu_lista) == 0
                and len(colidiu_blocos) == 0
            ):
                return

    def ativar_alerta(self):
        self.alerta_dano = True
        self.tempo_alerta = 0.7

    def on_draw(self):
        self.clear()

        arcade.draw_texture_rect(
            self.fundo,
            arcade.LBWH(0, 0, LARGURA, ALTURA),
        )

        self.lista_blocos.draw()
        self.lista_moedas.draw()
        self.lista_inimigos.draw()
        self.lista_inimigo_especial.draw()
        self.lista_jogador.draw()

        arcade.draw_text(
            f"Pontos: {self.pontos}",
            15,
            570,
            arcade.color.WHITE,
            16,
        )

        arcade.draw_text(
            f"Tempo: {self.tempo:.1f} segundos",
            15,
            545,
            arcade.color.WHITE,
            14,
        )

        if self.alerta_dano:
            desenhar_texto_central(
                "DANO RECEBIDO! -1 PONTO",
                510,
                20,
                arcade.color.RED,
            )

    def on_update(self, delta_time):
        self.tempo += delta_time

        self.lista_moedas.update(delta_time)
        self.lista_inimigos.update(delta_time)
        self.lista_inimigo_especial.update(delta_time)

        self.physics_engine.update()
        self.jogador.update(delta_time)

        if self.jogador.left < 0:
            self.jogador.left = 0
        if self.jogador.right > LARGURA:
            self.jogador.right = LARGURA

        if self.tempo_alerta > 0:
            self.tempo_alerta -= delta_time
            if self.tempo_alerta <= 0:
                self.alerta_dano = False

        if self.tempo_sem_novo_dano > 0:
            self.tempo_sem_novo_dano -= delta_time

        moedas_coletadas = arcade.check_for_collision_with_list(
            self.jogador,
            self.lista_moedas,
        )

        for moeda in moedas_coletadas:
            if isinstance(moeda, MoedaEspecial):
                self.pontos += PONTOS_MOEDA_ESPECIAL
            else:
                self.pontos += 1

            moeda.remove_from_sprite_lists()

        inimigos_atingidos = arcade.check_for_collision_with_list(
            self.jogador,
            self.lista_inimigos,
        )

        if len(inimigos_atingidos) > 0 and self.tempo_sem_novo_dano <= 0:
            self.pontos -= 1
            self.tempo_sem_novo_dano = 1.0
            self.ativar_alerta()

        inimigo_especial_atingido = arcade.check_for_collision_with_list(
            self.jogador,
            self.lista_inimigo_especial,
        )

        if len(inimigo_especial_atingido) > 0:
            self.pontos -= 1
            self.ativar_alerta()
            self.posicionar_sem_colisao(
                self.inimigo_especial,
                self.lista_moedas,
            )

        if len(self.lista_moedas) == 0:
            self.window.show_view(TelaGameOver(self.pontos, self.tempo))

    def on_key_press(self, key, modifiers):
        if key == arcade.key.LEFT or key == arcade.key.A:
            self.jogador.change_x = -VELOCIDADE_JOGADOR

        elif key == arcade.key.RIGHT or key == arcade.key.D:
            self.jogador.change_x = VELOCIDADE_JOGADOR

        elif key in (arcade.key.SPACE, arcade.key.UP, arcade.key.W):
            if self.physics_engine.can_jump():
                self.jogador.change_y = FORCA_PULO

        elif key == arcade.key.ESCAPE:
            self.window.show_view(TelaMenu())

    def on_key_release(self, key, modifiers):
        if key in (
            arcade.key.LEFT,
            arcade.key.RIGHT,
            arcade.key.A,
            arcade.key.D,
        ):
            self.jogador.change_x = 0


class TelaGameOver(arcade.View):
    def __init__(self, pontos, tempo):
        super().__init__()
        self.pontos = pontos
        self.tempo = tempo

        self.nome_jogador = ""
        self.salvo = False
        self.mensagem = "Digite seu nome e pressione ENTER para salvar."

    def on_show_view(self):
        arcade.set_background_color(arcade.color.AMAZON)

    def on_draw(self):
        self.clear()

        if self.pontos == PONTUACAO_MAXIMA:
            desenhar_texto_central(
                "VITÓRIA PERFEITA!",
                500,
                32,
                arcade.color.GOLD,
            )
        else:
            desenhar_texto_central(
                "PARABÉNS! JOGO CONCLUÍDO",
                500,
                28,
                arcade.color.YELLOW,
            )

        desenhar_texto_central(
            f"Pontuação final: {self.pontos}",
            410,
            20,
        )
        desenhar_texto_central(
            f"Tempo total: {self.tempo:.1f} segundos",
            375,
            18,
        )

        if not self.salvo:
            desenhar_texto_central(
                "NOME DO JOGADOR:",
                300,
                16,
                arcade.color.LIGHT_GRAY,
            )

            nome_visivel = self.nome_jogador if self.nome_jogador else "_"
            desenhar_texto_central(
                nome_visivel,
                255,
                24,
                arcade.color.WHITE,
            )

            desenhar_texto_central(
                self.mensagem,
                205,
                15,
                arcade.color.LIGHT_GRAY,
            )
        else:
            desenhar_texto_central(
                "Pontuação salva no ranking!",
                285,
                20,
                arcade.color.GREEN_YELLOW,
            )

            desenhar_texto_central(
                "[R] Ranking   |   [J] Jogar novamente   |   [M] Menu",
                190,
                15,
                arcade.color.LIGHT_GRAY,
            )

    def on_text(self, text):
        if self.salvo:
            return

        if text.isprintable() and len(self.nome_jogador) < 20:
            self.nome_jogador += text

    def on_key_press(self, key, modifiers):
        if not self.salvo:
            if key == arcade.key.BACKSPACE:
                self.nome_jogador = self.nome_jogador[:-1]

            elif key == arcade.key.ENTER:
                nome = self.nome_jogador.strip()

                if not nome:
                    self.mensagem = "Digite pelo menos 1 caractere antes de salvar."
                    return

                Pontuacao.create(
                    nome_jogador=nome,
                    pontos=self.pontos,
                    tempo_partida=self.tempo,
                )

                self.salvo = True
                self.mensagem = "Registro salvo com sucesso."

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


if __name__ == "__main__":
    main()
