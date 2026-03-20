# list_edge_voices.py - LISTA VOZES REAIS DO EDGE TTS
"""
Lista todas as vozes realmente disponíveis no Edge TTS.
Útil para verificar os nomes corretos.
"""

import asyncio


async def list_voices():
    """Lista todas as vozes do Edge TTS."""
    try:
        import edge_tts
    except ImportError:
        print("❌ edge-tts não instalado!")
        print("Instale com: pip install edge-tts")
        return

    print("=" * 70)
    print("LISTANDO TODAS AS VOZES EDGE TTS")
    print("=" * 70)
    print()

    # Lista vozes
    voices = await edge_tts.list_voices()

    # Filtra vozes em português brasileiro
    pt_br_voices = [v for v in voices if v["Locale"].startswith("pt-BR")]

    print(f"🇧🇷 Encontradas {len(pt_br_voices)} vozes em Português Brasileiro:")
    print()

    # Separa por gênero
    female = [v for v in pt_br_voices if v["Gender"] == "Female"]
    male = [v for v in pt_br_voices if v["Gender"] == "Male"]

    print("FEMININAS:")
    print("-" * 70)
    for v in female:
        name = v["ShortName"]
        friendly = v["FriendlyName"]
        print(f"  {name}")
        print(f"    Nome amigável: {friendly}")
        print()

    print("MASCULINAS:")
    print("-" * 70)
    for v in male:
        name = v["ShortName"]
        friendly = v["FriendlyName"]
        print(f"  {name}")
        print(f"    Nome amigável: {friendly}")
        print()

    print("=" * 70)
    print("DICIONÁRIO ATUALIZADO PARA COPIAR:")
    print("=" * 70)
    print()
    print("BRAZILIAN_VOICES = {")
    print("    # Femininas")
    for v in female:
        short = v["ShortName"]
        key = short.replace("pt-BR-", "").replace("Neural", "").lower()
        print(f'    "{key}": "{short}",')

    print("\n    # Masculinas")
    for v in male:
        short = v["ShortName"]
        key = short.replace("pt-BR-", "").replace("Neural", "").lower()
        print(f'    "{key}": "{short}",')

    print("}")
    print()


if __name__ == "__main__":
    asyncio.run(list_voices())
