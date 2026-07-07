# verificar_vozes_reais.py - LISTA VOZES REAIS DO EDGE TTS
"""
Conecta na API do Edge TTS e lista as vozes REALMENTE disponíveis.
"""

import asyncio


async def listar_vozes_reais():
    """Lista vozes reais disponíveis agora."""
    try:
        import edge_tts
    except ImportError:
        print("❌ edge-tts não instalado!")
        return

    print("=" * 70)
    print("CONECTANDO À API DO EDGE TTS...")
    print("=" * 70)
    print()

    try:
        # Lista todas as vozes
        vozes = await edge_tts.list_voices()

        # Filtra português brasileiro
        pt_br = [v for v in vozes if v["Locale"].startswith("pt-BR")]

        print(f"✅ Encontradas {len(pt_br)} vozes em Português Brasileiro")
        print()

        # Separa por gênero
        femininas = [v for v in pt_br if v["Gender"] == "Female"]
        masculinas = [v for v in pt_br if v["Gender"] == "Male"]

        print("=" * 70)
        print("VOZES FEMININAS (Recomendadas para EVE)")
        print("=" * 70)
        print()

        for v in femininas:
            nome_curto = v["ShortName"]
            nome_amigavel = v["FriendlyName"]
            print(f"✅ {nome_curto}")
            print(f"   Nome: {nome_amigavel}")
            print()

        print("=" * 70)
        print("VOZES MASCULINAS")
        print("=" * 70)
        print()

        for v in masculinas:
            nome_curto = v["ShortName"]
            nome_amigavel = v["FriendlyName"]
            print(f"✅ {nome_curto}")
            print(f"   Nome: {nome_amigavel}")
            print()

        # Cria dicionário atualizado
        print("=" * 70)
        print("DICIONÁRIO PARA USAR NO CÓDIGO:")
        print("=" * 70)
        print()
        print("VOZES_FEMININAS = {")
        for v in femininas:
            nome = v["ShortName"].replace("pt-BR-", "").replace("Neural", "")
            print(f'    "{nome}": "{v["ShortName"]}",')
        print("}")
        print()

        print("VOZES_MASCULINAS = {")
        for v in masculinas:
            nome = v["ShortName"].replace("pt-BR-", "").replace("Neural", "")
            print(f'    "{nome}": "{v["ShortName"]}",')
        print("}")
        print()

    except Exception as e:
        print(f"❌ Erro ao listar vozes: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(listar_vozes_reais())
