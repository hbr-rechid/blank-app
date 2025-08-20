#############################################################################
##  Em caso de dúvidas, entrar em contato com marcos.trindade@hidrobr.com  ##
#############################################################################

###################################################################################################
##               INSTRUÇÕES PARA AJUSTE RÁPIDO DO LAYOUT PARA APRESENTAÇÃO                       ##
##                                                                                               ##
##  Este painel foi desenhado para ser flexível. Caso a tela da apresentação seja maior ou       ##
##  menor, altere os valores abaixo para garantir a melhor visualização.                         ##
##                                                                                               ##
##  Recomenda-se colocar a página do navegador em fullscreen, pode-se usar a tecla F11, ou,      ##
##  no Google Chrome, o botão de tela cheia no menu de três pontos no canto superior direito.    ##
##  Alternativamente, para sair do modo fullscreen, pode-se pressionar a tecla ESC ou F11.       ##
##                                                                                               ##
###################################################################################################

# --- 0. CAMINHOS DOS ARQUIVOS (EDITÁVEL) ---
# Para "burlar" a necessidade de re-upload após um F5, você pode definir os caminhos locais
# para os seus arquivos .zip aqui. O aplicativo tentará carregá-los automaticamente.
# Se o caminho for deixado como "" ou o arquivo não for encontrado, o botão de upload aparecerá.
# Exemplo de caminho no Windows: "C:\\Users\\SeuUsuario\\Documentos\\mapas\\ZAS.zip"

ZAS_FILE_PATH = "ZAS_Irape.zip"
MUNICIPIOS_FILE_PATH = "Municipios_Irape.zip"
# Para os PEs, defina o caminho e o tipo ('shp' para shapefile .zip ou 'xlsx' para Excel) ### Priorizar '.zip'
PE_FILE_PATH = "PEs_Irape.zip"
PE_FILE_TYPE = "zip"


# --- 1. AJUSTES GERAIS DE ALTURA (em pixels) ---
# Altere os valores numéricos destas variáveis para ajustar a altura das seções principais.
# Altura da seção que contém o MAPA INTERATIVO. Aumente para um mapa mais alto.
# - Linha ~81: MAP_SECTION_HEIGHT_PX = 365 (ficou bom com o valor '315' na TV da HBR e com a resolução da pg. em 67% [segurar 'ctrl' + scroll do mouse p/ baixo])

# Altura da primeira linha de conteúdo, que afeta diretamente a altura do GRÁFICO DE BARRAS.
# - Linha ~82: TOP_DATA_ROW_CONTENT_HEIGHT_PX = 270

# --- 2. AJUSTES DE LARGURA DAS COLUNAS (Proporcional) ---
# A largura das seções é definida pela função st.columns([ ... ]).
# Os números dentro da lista são PROPORÇÕES. Mudar esses valores altera a largura relativa das colunas.
# Para ajustar, procure pelas seguintes linhas no código:
#
# - Linha ~600: st.columns([1, 3, 1]) -> Controla as colunas dos Logos e Título Principal.
# - Linha ~628: st.columns([0.07, 0.13, 0.5]) -> Controla as colunas de "Visão Geral", "Visão Detalhada" e o Gráfico.
# - Linha ~722: st.columns([0.3, 0.3, 0.3]) -> Controla as colunas do "Título do Mapa", "Filtro de Município" e "Legenda".
# --- 3. AJUSTES DE COMPONENTES ESPECÍFICOS (Requerem mais atenção) ---
# Alguns tamanhos são definidos diretamente no código ou no bloco de CSS no final.
#
# - TAMANHO DOS LOGOS: Na linha ~603, o tamanho é sugerido por `width=100`.
#   No final do arquivo, na linha ~1032 o CSS `max-height: 50px;` também pode limitar a altura.
#
# - ALTURA DA CAIXA DE TEXTO (PEs Manuais): Na linha ~704, definida por `height=TOP_DATA_ROW_CONTENT_HEIGHT_PX`.
#
# - TAMANHO DO FILTRO DE MUNICÍPIO: Este é um ajuste delicado, feito no bloco de CSS no final do código.
#   Procure pelo seletor `div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:first-child`
#   e altere os valores de:
#     - `height: 35px !important;` -> Altura da caixa de seleção (linha ~1095).
#     - `width: 180px;` -> Largura da caixa de seleção (linha ~1097).
# --- FIM DAS INSTRUÇÕES ---

import streamlit as st
import pandas as pd
import geopandas
import folium
from streamlit_folium import st_folium
import plotly.express as px
import zipfile
import tempfile
import os
import branca  # Necessário para a legenda HTML no mapa
from streamlit_local_storage import LocalStorage  # Biblioteca para persistir dados no navegador
import numpy as np  # Importado para cálculos de zoom do mapa
from io import BytesIO

# --- Paleta de Cores da Empresa ---
COLOR_PRIMARY = "#135D79"
COLOR_SECONDARY = "#169674"
COLOR_WHITE = "#FFFFFF"

# --- Definindo alturas fixas para as seções ---
MAP_SECTION_HEIGHT_PX = 485  # Mude conforme o tamanho do monitor --- 315 na TV da HBR e resolução da pg. de 67%
TOP_DATA_ROW_CONTENT_HEIGHT_PX = 270  # Mude conforme o tamanho do monitor


# --- Funções Auxiliares ---
def parse_pe_data(data_string: str) -> pd.DataFrame:
    """
    Analisa dados de Ponto de Encontro (PE) inseridos manualmente.
    Argumentos:
    data_string: Uma string onde cada linha representa um PE
    no formato "Nome | Latitude | Longitude".

    Retorna:
    Um DataFrame Pandas com colunas ['Nome', 'Latitude', 'Longitude'].
    """
    pes_list = []
    for line in data_string.strip().split('\n'):
        if '|' in line:  # Verifica se o delimitador está presente
            parts = line.split('|')
            if len(parts) == 3:
                try:
                    name = parts[0].strip()
                    lat = float(parts[1].strip().replace(',', '.'))  # Substitui vírgula por ponto para conversão float
                    lon = float(parts[2].strip().replace(',', '.'))  # Substitui vírgula por ponto para conversão float
                    pes_list.append({'Nome': name, 'Latitude': lat, 'Longitude': lon})
                except ValueError:
                    st.sidebar.warning(f"A linha '{line}' não pôde ser processada. Verifique o formato.")
            else:
                st.sidebar.warning(f"A linha '{line}' não tem o formato esperado (Nome | Lat | Lon).")
        elif line.strip(): # Evita avisos para linhas vazias
            st.sidebar.warning(f"A linha '{line}' não contém '|' como delimitador.")
    return pd.DataFrame(pes_list)

def load_pe_from_file(uploaded_file, file_type: str) -> pd.DataFrame:
    """
    Carrega dados de Ponto de Encontro (PE) de um arquivo enviado (XLSX ou Shapefile ZIP).

    Argumentos:
    uploaded_file: O arquivo enviado pelo usuário via st.file_uploader.
    file_type: Uma string que indica o tipo de arquivo ("xlsx" ou "shp").
    Retorna:
    Um DataFrame Pandas contendo dados de PE. Retorna um DataFrame vazio em caso de erro.
    """
    try:
        if file_type == "xlsx":
            df = pd.read_excel(uploaded_file)
        elif file_type == "shp":
            with tempfile.TemporaryDirectory() as tmpdir:  # Cria um diretório temporário
                with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
                    zip_ref.extractall(tmpdir)  # Extrai o conteúdo do zip
                shp_file_path = None
                for item in os.listdir(tmpdir):
                    if item.endswith(".shp"):  # Procura pelo arquivo .shp extraído
                        shp_file_path = os.path.join(tmpdir, item)
                        break
                if not shp_file_path:
                    st.sidebar.error("Nenhum arquivo .shp encontrado no .zip.")
                    return pd.DataFrame()
                gdf = geopandas.read_file(shp_file_path)
                if gdf.crs is None:
                    st.sidebar.warning("Shapefile dos PEs não possui CRS definido. Assumindo WGS84 (EPSG:4326).")
                    gdf.set_crs("EPSG:4326", inplace=True, allow_override=True)
                elif gdf.crs.to_string() != "EPSG:4326":
                    gdf = gdf.to_crs("EPSG:4326")  # Reprojeta para WGS84 se necessário
                df = pd.DataFrame()
                df['geometry'] = gdf.geometry  # Adiciona a coluna de geometria
                df['Longitude'] = gdf.geometry.x
                df['Latitude'] = gdf.geometry.y
                for col in gdf.columns:
                    if col not in ['geometry', 'Longitude', 'Latitude']:  # Adiciona outras colunas do shapefile
                        df[col] = gdf[col]
        else:
            return pd.DataFrame()

        st.session_state.uploaded_pe_df_columns = df.columns.tolist()
        return df

    except Exception as e:
        st.sidebar.error(f"Erro ao carregar o arquivo de PEs: {e}")
        return pd.DataFrame()

# --- INÍCIO: NOVAS FUNÇÕES PARA CARREGAR DADOS DE UM CAMINHO LOCAL ---
def load_pe_from_file_from_path(file_path: str, file_type: str) -> pd.DataFrame:
    """Carrega dados de PE (XLSX ou SHP) a partir de um caminho de arquivo local."""
    try:
        with open(file_path, "rb") as f:
            # A função original espera um objeto de arquivo, então podemos passar diretamente
            return load_pe_from_file(f, file_type)
    except FileNotFoundError:
        st.sidebar.error(f"Arquivo de PE não encontrado no caminho: {file_path}")
        return pd.DataFrame()
    except Exception as e:
        st.sidebar.error(f"Erro ao carregar o arquivo de PEs do caminho '{file_path}': {e}")
        return pd.DataFrame()

def load_generic_shapefile_from_path(file_path: str, layer_name: str) -> geopandas.GeoDataFrame | None:
    """Carrega um shapefile genérico (.zip) a partir de um caminho de arquivo local."""
    try:
        with open(file_path, "rb") as f:
            # A função original espera um objeto de arquivo, podemos criar um objeto simulado simples
            uploaded_file_mock = BytesIO(f.read())
            uploaded_file_mock.name = os.path.basename(file_path)  # Adiciona o atributo .name
            return load_generic_shapefile(uploaded_file_mock, layer_name)
    except FileNotFoundError:
        st.sidebar.error(f"Shapefile de {layer_name} não encontrado no caminho: {file_path}")
        return None
    except Exception as e:
        st.sidebar.error(f"Erro ao carregar shapefile de {layer_name} do caminho '{file_path}': {e}")
        return None
# --- FIM: NOVAS FUNÇÕES PARA CARREGAR DADOS DE UM CAMINHO LOCAL ---


def load_generic_shapefile(uploaded_file, layer_name: str) -> geopandas.GeoDataFrame | None:
    """
    Carrega dados de um arquivo Shapefile (.zip) genérico e o converte para EPSG:4326.
    Argumentos:
    uploaded_file: O arquivo .zip enviado pelo usuário.
    layer_name: Nome descritivo da camada para mensagens de erro/aviso (e.g., "ZAS", "Municípios").
    Retorna:
    Um GeoDataFrame com os dados do shapefile em EPSG:4326, ou None em caso de erro.
    """
    if uploaded_file is None:
        return None
    try:
        # Para lidar tanto com arquivos carregados via uploader quanto com BytesIO do carregamento local
        if hasattr(uploaded_file, 'getvalue'):
            file_bytes = uploaded_file.getvalue()
        else:
            uploaded_file.seek(0)
            file_bytes = uploaded_file.read()

        with tempfile.TemporaryDirectory() as tmpdir:  # Utiliza um diretório temporário para extração
            temp_zip_path = os.path.join(tmpdir, "data.zip")
            with open(temp_zip_path, "wb") as f:
                f.write(file_bytes)  # Salva o arquivo .zip temporariamente

            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                zip_ref.extractall(tmpdir)  # Extrai todos os arquivos do .zip

            shp_file_path = None
            # Busca recursiva para encontrar o .shp em subdiretórios
            for root, dirs, files in os.walk(tmpdir):
                for file in files:
                    if file.endswith(".shp"):
                        shp_file_path = os.path.join(root, file)
                        break
                if shp_file_path:
                    break

            if shp_file_path:
                gdf = geopandas.read_file(shp_file_path)  # Lê o shapefile usando GeoPandas
                if gdf.crs is None:  # Verifica o sistema de referência de coordenadas (CRS)
                    st.sidebar.warning(f"Shapefile de {layer_name} não possui CRS definido. Assumindo WGS84 (EPSG:4326).")
                    gdf.set_crs("EPSG:4326", inplace=True, allow_override=True)
                elif gdf.crs.to_string() != "EPSG:4326":  # Se não for WGS84, converte
                    try:
                        gdf = gdf.to_crs("EPSG:4326")
                    except Exception as e_crs:
                        st.sidebar.error(f"Erro ao reprojetar {layer_name} para EPSG:4326: {e_crs}")
                        return None
                if not gdf.empty:  # Verifica se o GeoDataFrame não está vazio
                    return gdf
                else:
                    st.sidebar.warning(f"O GeoDataFrame de {layer_name} está vazio ou não pôde ser processado.")
                    return None
            else:
                st.sidebar.error(f"Nenhum arquivo .shp encontrado no .zip de {layer_name}.")
                return None
    except Exception as e:
        st.sidebar.error(f"Erro ao processar o shapefile de {layer_name}: {e}")
        return None


# --- Configurações Iniciais da Página ---
st.set_page_config(
    page_title=st.session_state.get("app_title", "Dashboard de Simulado PAE"),
    page_icon="📊",  # Ícone da página
    layout="wide"  # Define o layout da página como "wide" (largo)
)

# --- INÍCIO: LÓGICA PARA CARREGAR ESTADO SALVO (LocalStorage) ---
# Instancia o objeto do LocalStorage para interagir com o navegador
localS = LocalStorage()

# Define uma chave única para salvar o estado deste aplicativo
APP_STATE_KEY = "pae_dashboard_state_hbr"

# Na inicialização do app, tenta carregar o estado salvo no navegador
if 'state_loaded' not in st.session_state:
    try:
        # Tenta obter o estado salvo
        saved_state = localS.getItem(APP_STATE_KEY)
        if saved_state:
            st.session_state.update(saved_state)
            # Converte a lista salva de volta para frozenset para a lógica de comparação funcionar
            if 'previous_pe_names_for_inputs' in st.session_state and isinstance(st.session_state.get('previous_pe_names_for_inputs'), list):
                st.session_state.previous_pe_names_for_inputs = frozenset(st.session_state.previous_pe_names_for_inputs)
    except Exception as e:
        # Se qualquer erro ocorrer (incluindo o TypeError), avisa e continua com um estado limpo
        st.warning(f"Não foi possível carregar o estado salvo. Um novo estado será criado. Erro: {e}")
    
    # Garante que a flag seja definida para não tentar carregar novamente
    st.session_state.state_loaded = True
# --- FIM: LÓGICA PARA CARREGAR ESTADO SALVO (LocalStorage) ---


# --- Sidebar para Inputs ---
st.sidebar.header("⚙️ Configurações e Entradas")

# 1. Configurações Gerais do Dashboard
st.sidebar.subheader("Identidade Visual e Títulos")
st.session_state.app_title = st.sidebar.text_input("Título Principal do Dashboard", st.session_state.get("app_title", "Painel de Acompanhamento - Simulado TCS"))
st.session_state.organizer_name = st.sidebar.text_input("Nome da Empresa Organizadora", st.session_state.get("organizer_name", ""))
st.session_state.organizer_logo_url = st.sidebar.text_input("URL do Logo da Organizadora", st.session_state.get("organizer_logo_url", "https://www.hidrobr.com/wp-content/uploads/2023/09/HidroBR_logo2.png"))
st.session_state.client_name = st.sidebar.text_input("Nome da Empresa Cliente", st.session_state.get("client_name", ""))
st.session_state.client_logo_url = st.sidebar.text_input("URL do Logo do Cliente", st.session_state.get("client_logo_url", "https://www.cemig.com.br/wp-content/uploads/2023/08/logo-cemig.png"))

# 2. Upload da Zona de Autossalvamento (ZAS)
st.sidebar.markdown("---")
st.sidebar.subheader("Upload da Zona de Autossalvamento (ZAS)")

# --- Lógica de Carregamento da ZAS (Automático ou Manual) ---
gdf_zas = None
if 'gdf_zas_processed' not in st.session_state:
    st.session_state.gdf_zas_processed = False

# Tenta carregar do caminho pré-definido primeiro
if ZAS_FILE_PATH and os.path.exists(ZAS_FILE_PATH) and ('gdf_zas' not in st.session_state or st.session_state.gdf_zas.empty):
    st.sidebar.info(f"Carregando ZAS do caminho local: {os.path.basename(ZAS_FILE_PATH)}")
    gdf_zas = load_generic_shapefile_from_path(ZAS_FILE_PATH, "ZAS")
    if gdf_zas is not None:
        st.session_state.gdf_zas = gdf_zas
        st.session_state.gdf_zas_processed = True
        st.sidebar.success("ZAS carregada do caminho local.")
# Se não houver caminho ou o arquivo não existir, mostra o uploader
else:
    uploaded_zas_file = st.sidebar.file_uploader(
        "Selecione o arquivo Shapefile (.zip contendo .shp, .dbf, .shx, etc.)",
        type=["zip"],
        key="zas_uploader"
    )
    if uploaded_zas_file and not st.session_state.gdf_zas_processed:
        gdf_zas = load_generic_shapefile(uploaded_zas_file, "ZAS")
        if gdf_zas is not None:
            st.session_state.gdf_zas = gdf_zas
            st.session_state.gdf_zas_processed = True
            st.sidebar.success("ZAS carregada e processada.")
        else:
            st.session_state.gdf_zas = None
            st.session_state.gdf_zas_processed = False

if 'gdf_zas' in st.session_state:
    gdf_zas = st.session_state.gdf_zas

# 3. Upload dos Municípios (Opcional)
st.sidebar.markdown("---")
st.sidebar.subheader("Upload dos Municípios (Opcional)")

# --- Lógica de Carregamento dos Municípios (Automático ou Manual) ---
if 'gdf_municipios' not in st.session_state:
    st.session_state.gdf_municipios = None
if 'municipios_processed' not in st.session_state:
    st.session_state.municipios_processed = False

temp_gdf_municipios = None
# Tenta carregar do caminho pré-definido primeiro
if MUNICIPIOS_FILE_PATH and os.path.exists(MUNICIPIOS_FILE_PATH) and ('gdf_municipios' not in st.session_state or st.session_state.gdf_municipios is None or st.session_state.gdf_municipios.empty):
    st.sidebar.info(f"Carregando municípios do caminho local: {os.path.basename(MUNICIPIOS_FILE_PATH)}")
    temp_gdf_municipios = load_generic_shapefile_from_path(MUNICIPIOS_FILE_PATH, "Municípios")
# Se não, mostra o uploader
else:
    uploaded_municipios_file = st.sidebar.file_uploader(
        "Upload Shapefile dos Municípios (.zip)",
        type=["zip"],
        key="municipios_uploader"
    )
    if uploaded_municipios_file:
        temp_gdf_municipios = load_generic_shapefile(uploaded_municipios_file, "Municípios")

# Processa o gdf de municípios (seja do path ou do upload)
if temp_gdf_municipios is not None:
    st.session_state.gdf_municipios = temp_gdf_municipios
    st.session_state.municipios_processed = True
    st.session_state.available_municipality_cols = temp_gdf_municipios.columns.tolist()
    if not st.session_state.get('municipio_load_success_displayed', False):
        st.sidebar.success("Shapefile de municípios carregado.")
        st.session_state.municipio_load_success_displayed = True
else:
    if st.session_state.get('gdf_municipios') is None:
        st.session_state.municipios_processed = False

# O restante da lógica para seleção de colunas de município permanece a mesma
if 'selected_municipality_name_col' not in st.session_state:
    st.session_state.selected_municipality_name_col = None

gdf_municipios_display = st.session_state.get('gdf_municipios', None)
selected_municipality_name_col = None
municipality_options = ["Todos os Municípios"]

if gdf_municipios_display is not None:
    municipality_name_cols = [col for col in gdf_municipios_display.columns if gdf_municipios_display[col].dtype == 'object' or gdf_municipios_display[col].dtype == 'string']
    default_mun_col_idx = 0
    available_cols_for_mun_name = st.session_state.get('available_municipality_cols', [])
    if available_cols_for_mun_name:
        common_names = ['MUNICIPIO', 'NOME_MUN', 'NM_MUN', 'NOMEMUNIC', 'NAME', 'NOME']
        for name in common_names:
            if name in available_cols_for_mun_name:
                default_mun_col_idx = available_cols_for_mun_name.index(name)
                break
            elif name.lower() in [c.lower() for c in available_cols_for_mun_name]:
                default_mun_col_idx = [c.lower() for c in available_cols_for_mun_name].index(name.lower())
                break
        if not municipality_name_cols and available_cols_for_mun_name:
            municipality_name_cols = available_cols_for_mun_name

    selected_municipality_name_col = st.sidebar.selectbox(
        "Coluna com Nome do Município:",
        options=municipality_name_cols if municipality_name_cols else available_cols_for_mun_name,
        index=default_mun_col_idx if (municipality_name_cols or available_cols_for_mun_name) else 0,
        key="selected_municipality_name_col_key",
        help="Selecione a coluna do arquivo shapefile que contém os nomes dos municípios."
    )
    st.session_state.selected_municipality_name_col = selected_municipality_name_col

    if selected_municipality_name_col and selected_municipality_name_col in gdf_municipios_display.columns:
        try:
            unique_municipalities = sorted(gdf_municipios_display[selected_municipality_name_col].astype(str).unique())
            municipality_options.extend(unique_municipalities)
        except Exception as e:
            st.sidebar.error(f"Não foi possível obter nomes de municípios da coluna '{selected_municipality_name_col}'. {e}")


# 4. Definição dos Pontos de Encontro (PEs)
st.sidebar.markdown("---")
st.sidebar.subheader("Dados dos Pontos de Encontro (PEs)")

# Inicializa o DataFrame e o estado de configuração
df_pe_initial = pd.DataFrame(columns=['Nome', 'Latitude', 'Longitude'])
if 'df_pe_configured' not in st.session_state:
    st.session_state.df_pe_configured = False

pe_data_processed = False
raw_uploaded_df = None
file_type_ext = "shp" # O único tipo agora é shapefile

# Tenta carregar do caminho pré-definido primeiro
# A condição foi simplificada para sempre tentar carregar o arquivo local se ele existir.
# A lógica subsequente irá decidir se usa este ou um arquivo de upload manual.
if PE_FILE_PATH and os.path.exists(PE_FILE_PATH) and PE_FILE_TYPE == 'zip':
    # Não exibe a mensagem de 'info' ainda para não poluir a interface.
    # Apenas carrega os dados se um arquivo de upload ainda não foi processado.
    if 'pe_file_uploader_shp' not in st.session_state or st.session_state.pe_file_uploader_shp is None:
        st.sidebar.info(f"Carregando PEs do caminho local: {os.path.basename(PE_FILE_PATH)}")
        raw_uploaded_df = load_pe_from_file_from_path(PE_FILE_PATH, file_type_ext)
# Se não houver caminho ou o arquivo não existir, mostra o uploader
else:
    uploaded_pe_file = st.sidebar.file_uploader(
        "Selecione o arquivo Shapefile (.zip)",
        type=["zip"],
        key="pe_file_uploader_shp"
    )
    if uploaded_pe_file:
        raw_uploaded_df = load_pe_from_file(uploaded_pe_file, file_type_ext)

# Se um arquivo foi carregado (do caminho ou do upload), processa os dados
if raw_uploaded_df is not None and not raw_uploaded_df.empty:
    cols = raw_uploaded_df.columns.tolist()
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Mapeamento de Colunas do Arquivo de PEs:**")

    # Lógica para encontrar as colunas por nome
    
    common_names = ['Nome', 'nome', 'Name', 'name', 'PE', 'PONTO']
    default_name_col_idx = 0 # Padrão, caso nenhuma seja encontrada
    # Procura por um nome comum na lista de colunas do arquivo
    for name in common_names:
        if name in cols:
            default_name_col_idx = cols.index(name)
            break
    default_lat_col_idx = cols.index("Latitude") if "Latitude" in cols else (cols.index("Lat") if "Lat" in cols else (1 if len(cols)>1 else 0))
    default_lon_col_idx = cols.index("Longitude") if "Longitude" in cols else (cols.index("Lon") if "Lon" in cols else (cols.index("Lng") if "Lng" in cols else (2 if len(cols)>2 else 0)))

    name_col = st.sidebar.selectbox("Coluna para 'Nome' do PE:", cols, index=default_name_col_idx, key="pe_name_col_select")
    lat_col = st.sidebar.selectbox("Coluna para 'Latitude':", cols, index=default_lat_col_idx, key="pe_lat_col_select")
    lon_col = st.sidebar.selectbox("Coluna para 'Longitude':", cols, index=default_lon_col_idx, key="pe_lon_col_select")

    # Processa os dados quando o botão é clicado ou se a configuração ainda não foi feita
    if st.sidebar.button("Processar PEs do Arquivo") or (raw_uploaded_df is not None and df_pe_initial.empty):
        try:
            df_pe_initial = pd.DataFrame({
                'Nome': raw_uploaded_df[name_col].astype(str),
                'Latitude': pd.to_numeric(raw_uploaded_df[lat_col]),
                'Longitude': pd.to_numeric(raw_uploaded_df[lon_col])
            })
            df_pe_initial.dropna(subset=['Latitude', 'Longitude'], inplace=True)
            st.session_state.df_pe_initial_backup = df_pe_initial.copy()
            st.session_state.df_pe_configured = not df_pe_initial.empty
            pe_data_processed = True
            if not df_pe_initial.empty:
                st.sidebar.success(f"{len(df_pe_initial)} PEs processados do arquivo.")
            else:
                 st.sidebar.warning("Nenhum PE válido encontrado no arquivo após mapeamento.")
        except Exception as e:
            st.sidebar.error(f"Erro ao mapear colunas: {e}")
            st.session_state.df_pe_configured = False


# Restaura PEs do backup se não foram processados novamente e o backup existe
if not pe_data_processed and 'df_pe_initial_backup' in st.session_state:
    df_pe_initial = st.session_state.df_pe_initial_backup.copy()

# Tenta carregar PEs manuais default se nada foi configurado ainda (primeira execução)
if df_pe_initial.empty and 'pe_data_raw_input_val' in st.session_state and not st.session_state.get('df_pe_configured', False):
    df_pe_initial = parse_pe_data(st.session_state.pe_data_raw_input_val)

# Lógica para resetar inputs de participantes/esperados se a lista de PEs mudar
current_pe_names = frozenset(df_pe_initial['Nome'].tolist()) if not df_pe_initial.empty else frozenset()
previous_pe_names = st.session_state.get('previous_pe_names_for_inputs', frozenset())

if current_pe_names != previous_pe_names:
    keys_to_delete = []
    for k in st.session_state.keys():
        if k.startswith('participantes_') or k.startswith('esperadas_') or k.startswith('widget_') or k.startswith('selected_pe_name_dashboard'):
            keys_to_delete.append(k)
    for k_del in keys_to_delete:
        del st.session_state[k_del]
    st.session_state.previous_pe_names_for_inputs = current_pe_names
    st.session_state.df_pe_configured = not df_pe_initial.empty

df_pe = pd.DataFrame()
if not df_pe_initial.empty:
    if df_pe_initial.index.name != 'Nome':
        try:
            df_pe_initial.set_index('Nome', inplace=True)
        except KeyError:
            st.error("Coluna 'Nome' não encontrada nos dados iniciais dos PEs para definir como índice.")
            df_pe_initial = pd.DataFrame()

    if not df_pe_initial.empty:
        df_pe = df_pe_initial.copy()

        st.sidebar.markdown("---")
        st.sidebar.subheader("Contagem por Ponto de Encontro")
        for pe_name in df_pe.index:
            with st.sidebar.expander(f"PE: {pe_name}", expanded=False):
                participantes_key_ss = f'participantes_{pe_name}'
                esperadas_key_ss = f'esperadas_{pe_name}'
                participantes_key_widget = f'widget_participantes_{pe_name}'
                esperadas_key_widget = f'widget_esperadas_{pe_name}'

                if participantes_key_ss not in st.session_state:
                    st.session_state[participantes_key_ss] = 0
                if esperadas_key_ss not in st.session_state:
                    st.session_state[esperadas_key_ss] = 1

                current_participantes = st.number_input(
                    f"Total de Participantes",
                    min_value=0,
                    value=st.session_state[participantes_key_ss],
                    key=participantes_key_widget,
                    help=f"Número de participantes que chegaram ao PE {pe_name}"
                )
                st.session_state[participantes_key_ss] = current_participantes

                current_esperadas = st.number_input(
                    f"Número de Pessoas Esperadas",
                    min_value=0,
                    value=st.session_state[esperadas_key_ss],
                    key=esperadas_key_widget,
                    help=f"Número de pessoas que eram esperadas no PE {pe_name}"
                )
                st.session_state[esperadas_key_ss] = current_esperadas

                df_pe.loc[pe_name, 'Total de Participantes'] = st.session_state[participantes_key_ss]
                df_pe.loc[pe_name, 'Número de Pessoas Esperadas'] = st.session_state[esperadas_key_ss]

        def calcular_efetividade(row):
            """Calcula a eficácia com base nos participantes e nas pessoas esperadas."""
            if row['Número de Pessoas Esperadas'] > 0:
                return (row['Total de Participantes'] / row['Número de Pessoas Esperadas']) * 100
            return 0.0
        df_pe['Efetividade (%)'] = df_pe.apply(calcular_efetividade, axis=1)

else:
    df_pe = pd.DataFrame(columns=['Nome', 'Latitude', 'Longitude', 'Total de Participantes', 'Número de Pessoas Esperadas', 'Efetividade (%)'])
    if 'Nome' not in df_pe.columns:
        df_pe = pd.DataFrame(columns=['Latitude', 'Longitude', 'Total de Participantes', 'Número de Pessoas Esperadas', 'Efetividade (%)'])
        df_pe.index.name = 'Nome'

if not df_pe.empty:
    df_pe_filtered = df_pe.copy()
    df_pe_filtered['Município'] = None

    if gdf_municipios_display is not None and selected_municipality_name_col and selected_municipality_name_col in gdf_municipios_display.columns:
        if 'Latitude' in df_pe.columns and 'Longitude' in df_pe.columns:
            try:
                gdf_pe_for_join = geopandas.GeoDataFrame(
                    df_pe.reset_index(),
                    geometry=geopandas.points_from_xy(df_pe['Longitude'], df_pe['Latitude']),
                    crs="EPSG:4326"
                )
                joined_gdf = geopandas.sjoin(
                    gdf_pe_for_join,
                    gdf_municipios_display[[selected_municipality_name_col, 'geometry']],
                    how="left", predicate="within"
                )
                joined_gdf.drop_duplicates(subset=['Nome'], keep='first', inplace=True)
                municipality_map = joined_gdf.set_index('Nome')[selected_municipality_name_col]
                df_pe_filtered['Município'] = df_pe_filtered.index.map(municipality_map)
            except Exception as e:
                st.error(f"Erro na junção espacial PEs-Municípios: {e}")
        else:
            st.warning("Colunas 'Latitude' ou 'Longitude' não encontradas nos dados dos PEs para junção espacial.")
else:
    df_pe_filtered = pd.DataFrame(columns=['Nome', 'Latitude', 'Longitude', 'Total de Participantes', 'Número de Pessoas Esperadas', 'Efetividade (%)', 'Município'])
    df_pe_filtered.set_index('Nome', inplace=True)

# --- FIM DA BARRA LATERAL (LÓGICA) ---


# --- LAYOUT PRINCIPAL DA PÁGINA ---
row1_col1, row1_col2, row1_col3 = st.columns([1, 3, 1])
with row1_col1:
    if st.session_state.get("organizer_logo_url"):
        st.image(st.session_state.organizer_logo_url, width=100)
    st.caption(st.session_state.get("organizer_name", ""))

with row1_col2:
    st.title(st.session_state.get("app_title", "Painel de Acompanhamento"))

with row1_col3:
    if st.session_state.get("client_logo_url"):
        st.image(st.session_state.client_logo_url, width=100)
    st.caption(st.session_state.get("client_name", ""))

selected_municipality_filter_value = st.session_state.get("selected_municipality_filter", "Todos os Municípios")
df_pe_display = df_pe_filtered.copy()

if selected_municipality_filter_value != "Todos os Municípios":
    if 'Município' in df_pe_filtered.columns:
        df_pe_display = df_pe_filtered[df_pe_filtered['Município'] == selected_municipality_filter_value].copy()
    else:
        if selected_municipality_filter_value != "Todos os Municípios":
            st.warning("Coluna 'Município' não encontrada para aplicar filtro. Verifique o upload e mapeamento.")

if df_pe_display.empty and not df_pe_filtered.empty and selected_municipality_filter_value != "Todos os Municípios":
    st.warning(f"Nenhum Ponto de Encontro encontrado para o município: {selected_municipality_filter_value}. O gráfico e as métricas refletem esta seleção.")

if not df_pe.empty:
    col_geral_metrics, col_single_pe, col_chart = st.columns([0.07, 0.13, 0.5])

    with col_geral_metrics:
        st.markdown("###### Visão Geral")
        total_participantes_geral = df_pe_display['Total de Participantes'].sum()
        total_esperados_geral = df_pe_display['Número de Pessoas Esperadas'].sum()
        efetividade_geral = (total_participantes_geral / total_esperados_geral * 100) if total_esperados_geral > 0 else 0

        st.metric(label="Total Participantes", value=f"{total_participantes_geral:,.0f}")
        st.metric(label="Total Esperado", value=f"{total_esperados_geral:,.0f}")
        st.metric(
            label="Efetividade Geral",
            value=f"{efetividade_geral:,.2f}%".replace(".", ",")
        )

    with col_single_pe:
        st.markdown("###### Visão Detalhada - Ponto de Encontro")
        pe_names_list_display = df_pe_display.index.tolist()
        if not pe_names_list_display:
            st.info("Nenhum PE disponível para seleção (após filtro).")
        else:
            current_selection_idx = 0
            prev_selected_pe = st.session_state.get('selected_pe_name_dashboard_selectbox')
            if prev_selected_pe in pe_names_list_display:
                current_selection_idx = pe_names_list_display.index(prev_selected_pe)
            else:
                st.session_state.selected_pe_name_dashboard_selectbox = pe_names_list_display[0]
                current_selection_idx = 0

            selected_pe_name = st.selectbox(
                "Selecione o Ponto de Encontro:",
                options=pe_names_list_display,
                index=current_selection_idx,
                key="selected_pe_name_dashboard_selectbox"
            )

            if selected_pe_name and selected_pe_name in df_pe_display.index:
                row_pe_data = df_pe_display.loc[selected_pe_name]
                st.markdown(f"<div class='pe-card'><h6>{selected_pe_name}</h6>", unsafe_allow_html=True)
                efetividade_val = row_pe_data['Efetividade (%)']
                efetividade_formatada = f"{efetividade_val:,.2f}".replace(".", ",")
                st.progress(min(int(efetividade_val), 100))
                st.caption(f"Efetividade: {efetividade_formatada}%")

                card_metric_col1, card_metric_col2 = st.columns(2)
                with card_metric_col1:
                    st.markdown(f"<p class='pe-card-metric-label'>Participantes</p>"
                                f"<p class='pe-card-metric-value'>{row_pe_data['Total de Participantes']:,.0f}</p>",
                                unsafe_allow_html=True)
                with card_metric_col2:
                    st.markdown(f"<p class='pe-card-metric-label'>Esperados</p>"
                                f"<p class='pe-card-metric-value pe-card-metric-value-alt'>{row_pe_data['Número de Pessoas Esperadas']:,.0f}</p>",
                                unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
            elif not df_pe_display.empty:
                st.warning("PE selecionado não encontrado nos dados filtrados. Por favor, selecione outro PE.")

    with col_chart:
        st.markdown("###### Participantes: Realizado vs. Esperado")
        if not df_pe_display.empty:
            df_melted_source = df_pe_display.reset_index()
            df_melted = df_melted_source.melt(
                id_vars=['Nome'],
                value_vars=['Total de Participantes', 'Número de Pessoas Esperadas'],
                var_name='Métrica', value_name='Quantidade'
            )
            fig_participantes_esperados = px.bar(
                df_melted, x='Nome', y='Quantidade', color='Métrica', barmode='group',
                color_discrete_map={
                    'Total de Participantes': COLOR_SECONDARY,
                    'Número de Pessoas Esperadas': COLOR_PRIMARY
                },
                labels={'Nome': 'Ponto de Encontro', 'Quantidade': 'Número de Pessoas'},
                text_auto=True
            )
            fig_participantes_esperados.update_layout(
                height=TOP_DATA_ROW_CONTENT_HEIGHT_PX,
                xaxis_title=None, yaxis_title="Número de Pessoas",
                plot_bgcolor=COLOR_WHITE, paper_bgcolor=COLOR_WHITE,
                font_color=COLOR_PRIMARY,
                xaxis=dict(tickfont=dict(color=COLOR_PRIMARY, size=16)),
                yaxis=dict(tickfont=dict(color=COLOR_PRIMARY, size=14)),
                legend_title_text='',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color=COLOR_PRIMARY, size=16)),
                margin=dict(t=20, b=0, l=0, r=0)
            )
            fig_participantes_esperados.update_yaxes(showgrid=True, gridwidth=0.5, gridcolor='LightGrey')
            fig_participantes_esperados.update_traces(textfont_size=18, textposition='inside')
            st.plotly_chart(fig_participantes_esperados, use_container_width=True)
        else:
            st.info("Nenhum dado para exibir no gráfico com o filtro atual.")

    st.markdown("---")

    col_map_title, col_map_filter_container, col_map_legend = st.columns([0.3, 0.3, 0.3])

    with col_map_title:
        st.subheader("🗺️ Mapa Interativo dos Pontos de Encontro")

    with col_map_filter_container:
        if len(municipality_options) > 1:
            label_col, select_col = st.columns([0.8, 1.2])
            with label_col:
                label_html = f"<div style='padding-top: 7px; text-align: right; padding-right: 5px; color: {COLOR_PRIMARY}; font-weight: bold;'>Filtrar por Município:</div>"
                st.markdown(label_html, unsafe_allow_html=True)
            with select_col:
                current_filter_index = 0
                if selected_municipality_filter_value in municipality_options:
                    current_filter_index = municipality_options.index(selected_municipality_filter_value)
                selected_municipality_filter = st.selectbox(
                    label=" ",
                    options=municipality_options,
                    key="selected_municipality_filter",
                    index=current_filter_index,
                    label_visibility="collapsed"
                )
        else:
            selected_municipality_filter = "Todos os Municípios"
            st.caption("Carregue municípios para filtrar.")

    with col_map_legend:
        legend_items_html = [
            f'<span style="color:blue; font-size:1.1em; vertical-align: middle; margin-right: 3px;">●</span> <span style="font-size:1em; vertical-align: middle; margin-right: 8px;">&ge; 75%</span>',
            f'<span style="color:green; font-size:1.1em; vertical-align: middle; margin-right: 3px;">●</span> <span style="font-size:1em; vertical-align: middle; margin-right: 8px;">50-74,9%</span>',
            f'<span style="color:orange; font-size:1.1em; vertical-align: middle; margin-right: 3px;">●</span> <span style="font-size:1em; vertical-align: middle; margin-right: 8px;">25-49,9%</span>',
            f'<span style="color:red; font-size:1.1em; vertical-align: middle; margin-right: 3px;">●</span> <span style="font-size:1em; vertical-align: middle; margin-right: 8px;">0-24,9%</span>',
            f'<span style="color:gray; font-size:1.1em; vertical-align: middle; margin-right: 3px;">●</span> <span style="font-size:0.9em; vertical-align: middle;">N/A</span>'
        ]
        horizontal_legend_html = f"""
        <div style="text-align: right; margin-top: 10px;">
            <span style="font-size:1em; color:{COLOR_PRIMARY}; font-weight:bold; vertical-align: middle; margin-right:8px;">Efetividade PE:</span>
            {''.join(f'<span style="display: inline-block; white-space: nowrap; vertical-align: middle;">{item}</span>' for item in legend_items_html)}
        </div>
        """
        st.markdown(horizontal_legend_html, unsafe_allow_html=True)

    # --- INÍCIO: LÓGICA DE CENTRALIZAÇÃO DINÂMICA DO MAPA ---
    gdf_zas_map = st.session_state.get('gdf_zas', None)

    # Prioridade 1: Centralizar na ZAS
    if gdf_zas_map is not None and isinstance(gdf_zas_map, geopandas.GeoDataFrame) and not gdf_zas_map.empty:
        bounds = gdf_zas_map.total_bounds  # Retorna (minx, miny, maxx, maxy)
        map_center_lon = (bounds[0] + bounds[2]) / 2
        map_center_lat = (bounds[1] + bounds[3]) / 2

        # Lógica para definir o zoom com base na extensão da ZAS
        lon_diff = abs(bounds[2] - bounds[0])
        lat_diff = abs(bounds[3] - bounds[1])
        max_diff = max(lon_diff, lat_diff)
        # Esta é uma fórmula empírica. Ajuste os valores se necessário.
        if max_diff > 0:
            zoom_level = 11 - np.log2(max_diff)
            zoom_start = min(max(int(zoom_level), 5), 16)  # Limita o zoom entre 5 e 16
        else:
            zoom_start = 13

    # Prioridade 2: Centralizar nos PEs se não houver ZAS
    elif not df_pe_filtered.empty:
        map_center_lat = df_pe_filtered['Latitude'].mean()
        map_center_lon = df_pe_filtered['Longitude'].mean()
        zoom_start = 11

    # Fallback: Posição padrão se não houver dados
    else:
        map_center_lat = -18.45
        map_center_lon = -48.00
        zoom_start = 10
    # --- FIM: LÓGICA DE CENTRALIZAÇÃO DINÂMICA DO MAPA ---

    m = folium.Map(
        location=[map_center_lat, map_center_lon],
        zoom_start=zoom_start,
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri &mdash; Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community"
    )

    gdf_municipios_map = st.session_state.get('gdf_municipios', None)
    if gdf_municipios_map is not None and isinstance(gdf_municipios_map, geopandas.GeoDataFrame) and not gdf_municipios_map.empty:
        municipio_name_col_map = st.session_state.get('selected_municipality_name_col', None)
        def style_function_municipio(feature):
            base_style = {'fillColor': '#808080', 'color': '#000000', 'weight': 0.5, 'fillOpacity': 0.1}
            current_filter = selected_municipality_filter
            try:
                if municipio_name_col_map and \
                   municipio_name_col_map in feature['properties'] and \
                   feature['properties'][municipio_name_col_map] == current_filter:
                    base_style['fillColor'] = COLOR_PRIMARY
                    base_style['fillOpacity'] = 0.3
                    base_style['color'] = COLOR_PRIMARY
                    base_style['weight'] = 1.5
            except Exception:
                pass
            return base_style
        tooltip_fields_mun = [municipio_name_col_map] if municipio_name_col_map and municipio_name_col_map in gdf_municipios_map.columns else []
        popup_mun = None
        if municipio_name_col_map and municipio_name_col_map in gdf_municipios_map.columns:
            popup_mun = folium.features.GeoJsonPopup(fields=[municipio_name_col_map], aliases=["Município:"])
        if tooltip_fields_mun:
            folium.GeoJson(
                gdf_municipios_map,
                name='Municípios',
                style_function=style_function_municipio,
                tooltip=folium.GeoJsonTooltip(fields=tooltip_fields_mun, aliases=["Município:"], sticky=False),
                popup=popup_mun
            ).add_to(m)
        else:
            folium.GeoJson(gdf_municipios_map, name='Municípios', style_function=style_function_municipio).add_to(m)

    if gdf_zas_map is not None and isinstance(gdf_zas_map, geopandas.GeoDataFrame) and not gdf_zas_map.empty:
        attribute_columns_zas = [col for col in gdf_zas_map.columns if col != gdf_zas_map.geometry.name]
        style_zas = {'fillColor': '#00c5ff', 'color': '#e41a1c', 'weight': 0.7, 'fillOpacity': 0.5}
        folium.GeoJson(
            gdf_zas_map, name='Zona de Autossalvamento (ZAS)', style_function=lambda x: style_zas,
            tooltip=folium.GeoJsonTooltip(fields=attribute_columns_zas, aliases=[f"{col}:" for col in attribute_columns_zas], sticky=False)
        ).add_to(m)

    for idx_name, row_pe_map in df_pe_display.iterrows():
        popup_html = f"""<div style="font-family: Arial, sans-serif; font-size: 12px; overflow-wrap: break-word;">
            <strong>PE:</strong> {idx_name}<br>
            <strong>Participantes:</strong> {row_pe_map['Total de Participantes']:,.0f}<br>
            <strong>Esperados:</strong> {row_pe_map['Número de Pessoas Esperadas']:,.0f}<br>
            <strong>Efetividade:</strong> {row_pe_map['Efetividade (%)']:.2f}%"""
        if 'Município' in row_pe_map and pd.notna(row_pe_map['Município']):
            popup_html += f"<br><strong>Município:</strong> {row_pe_map['Município']}</div>"
        else:
            popup_html += "</div>"
        efetividade_valor = row_pe_map['Efetividade (%)']
        pe_icon_color = 'gray'
        pe_icon_symbol = 'minus-sign'
        if row_pe_map['Número de Pessoas Esperadas'] > 0 or row_pe_map['Total de Participantes'] > 0:
            if efetividade_valor >= 75:
                pe_icon_color, pe_icon_symbol = 'blue', 'ok-sign'
            elif efetividade_valor >= 50:
                pe_icon_color, pe_icon_symbol = 'green', 'info-sign'
            elif efetividade_valor >= 25:
                pe_icon_color, pe_icon_symbol = 'orange', 'remove-sign'
            else:
                pe_icon_color, pe_icon_symbol = 'red', 'exclamation-sign'
        folium.Marker(
            location=[row_pe_map['Latitude'], row_pe_map['Longitude']],
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"{idx_name} | Efetividade: {row_pe_map['Efetividade (%)']:.1f}%",
            icon=folium.Icon(color=pe_icon_color, icon=pe_icon_symbol, prefix='glyphicon')
        ).add_to(m)

    if (gdf_zas_map is not None and not gdf_zas_map.empty) or \
       (gdf_municipios_map is not None and not gdf_municipios_map.empty):
        folium.LayerControl(collapsed=True).add_to(m)

    # Criar um contêiner para renderizar o mapa e o rodapé juntos
    # Solução Estrutural Proposta

    # Criar um contêiner APENAS para o mapa
    with st.container():
        st_folium(m, use_container_width=True)

    # Renderiza o rodapé FORA e DEPOIS do contêiner do mapa
    st.markdown(
        f"""
        <div style="margin-top: 0rem; margin-bottom: 0rem;">
            <p style='text-align:center; color:{COLOR_PRIMARY}; font-size:0.9em;'>
                {st.session_state.get('app_title', 'Painel de Simulado PAE')} |
                Desenvolvido para visualização otimizada de dados.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    # --- FIM DA MUDANÇA ESTRUTURAL ---

else:
    st.info("👈 Configure os Pontos de Encontro na barra lateral para visualizar o dashboard. Se já configurado, verifique os filtros de município ou os dados de entrada.")
    # Adicione também o rodapé aqui para que ele apareça mesmo quando não há mapa
    st.markdown(
        f"""
        <div style="margin-top: 1rem; margin-bottom: 0rem;">
            <p style='text-align:center; color:{COLOR_PRIMARY}; font-size:0.9em;'>
                {st.session_state.get('app_title', 'Painel de Simulado PAE')} | Desenvolvido para visualização otimizada de dados.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
# --- INÍCIO: LÓGICA PARA SALVAR ESTADO ATUAL (LocalStorage) ---
# No final de cada execução do script, coletamos os dados importantes do session_state e os salvamos no navegador do usuário.

# Lista de chaves de texto/números simples que queremos que persistam.
# **NÃO** inclua objetos grandes como DataFrames (ex: 'gdf_zas', 'df_pe_initial_backup').
keys_to_persist = [
    "app_title", "organizer_name", "organizer_logo_url", "client_name", "client_logo_url",
    "pe_input_method_idx", "pe_data_raw_input_val",
    "selected_municipality_name_col", "selected_municipality_filter",
    "pe_name_col_select", "pe_lat_col_select", "pe_lon_col_select",
    "previous_pe_names_for_inputs",
    "df_pe_configured"
]

# Dicionário que conterá todo o estado a ser salvo.
state_to_save = {}
# Itera sobre as chaves que queremos salvar
for key in keys_to_persist:
    if key in st.session_state:
        value = st.session_state[key]
        # ---- INÍCIO DA MODIFICAÇÃO ----
        # Se a chave for a do frozenset, converte para lista antes de salvar
        if key == 'previous_pe_names_for_inputs' and isinstance(value, frozenset):
            state_to_save[key] = list(value)
        else:
            state_to_save[key] = value

# Adiciona dinamicamente os valores de contagem de cada PE ao dicionário.
for key in st.session_state.keys():
    if key.startswith('participantes_') or key.startswith('esperadas_'):
        state_to_save[key] = st.session_state[key]

# Salva o dicionário de estado no localStorage, sobrescrevendo a versão anterior.
localS.setItem(APP_STATE_KEY, state_to_save)
# --- FIM: LÓGICA PARA SALVAR ESTADO ATUAL (LocalStorage) ---


# CSS customizado para o aplicativo
custom_css = f"""
<style>
    /* --- ESTILOS GERAIS DO CONTAINER PRINCIPAL --- */
    .main .block-container {{
        padding-top: 1.06rem; /* Espaçamento superior do container principal da página. Ajuste se precisar de mais ou menos espaço no topo. */
        padding-bottom: 1rem; /* Espaçamento inferior do container principal da página. */
    }}

    /* --- ESTILOS PARA SUBTÍTULOS (H6) EM BLOCOS VERTICAIS ESPECÍFICOS --- */
    div[data-testid="stVerticalBlock"] div[data-testid="stMarkdownContainer"] h6 {{
        margin-top: 0rem; /* Remove margem superior do h6 para economizar espaço. */
        margin-bottom: 0.1rem; /* Margem inferior pequena para separar do conteúdo abaixo. */
        color: {COLOR_PRIMARY}; /* Define a cor do texto do h6 para a cor primária da empresa. */
        font-size: 1.05em; /* Tamanho da fonte do h6. Pode aumentar ou diminuir conforme a necessidade. */
    }}

    /* --- ESTILOS PARA COMPONENTES DE MÉTRICA DO STREAMLIT --- */
    div[data-testid="stVerticalBlock"] div.stMetric {{
        padding: 8px 10px; /* Espaçamento interno (vertical, horizontal) das caixas de métrica. */
        margin-bottom: 8px; /* Margem inferior para separar métricas empilhadas. */
    }}
    div[data-testid="stVerticalBlock"] div.stMetric label {{
        font-size: 0.85em; /* Tamanho da fonte do rótulo da métrica (ex: "Total Participantes"). */
    }}
     div[data-testid="stVerticalBlock"] div.stMetric div[data-testid="stMetricValue"] {{
        font-size: 1.5em; /* Tamanho da fonte do valor da métrica (ex: "1,234"). Ajuste para maior destaque. */
    }}

    /* --- ESTILOS PARA OS CARDS DE PONTOS DE ENCONTRO (PE) --- */
    .pe-card {{
        border: 1px solid #e0e0e0; /* Borda fina cinza ao redor do card. */
        border-left: 5px solid {COLOR_PRIMARY}; /* Borda esquerda mais espessa na cor primária, para destaque. */
        border-radius: 5px; /* Cantos arredondados para o card. */
        padding: 10px 12px; /* Espaçamento interno do card. */
        margin-bottom: 10px; /* Margem inferior para separar cards. */
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05); /* Sombra sutil para dar profundidade ao card. */
        background-color: {COLOR_WHITE}; /* Cor de fundo do card. */
    }}
    .pe-card h6 {{ /* Título dentro do card do PE */
        margin-top: 0; /* Remove margem superior. */
        margin-bottom: 0.4rem; /* Margem inferior para separar do próximo elemento. */
        font-size: 1em; /* Tamanho da fonte do título do card. */
        font-weight: bold; /* Texto em negrito. */
        color: {COLOR_PRIMARY}; /* Cor do texto do título do card. */
    }}
    .pe-card .stProgress {{ /* Barra de progresso dentro do card */
        margin-bottom: 0.3rem; /* Pequena margem inferior. */
    }}
    .pe-card p.caption {{ /* Texto de legenda (caption) dentro do card */
        font-size: 0.8em; /* Tamanho da fonte da legenda. */
        margin-bottom: 0.5rem; /* Margem inferior. */
    }}
    .pe-card-metric-label {{ /* Rótulo de métrica dentro do card (ex: "Participantes") */
        font-size: 0.85em; /* Tamanho da fonte. */
        color: #495057; /* Cor do texto (cinza escuro). */
        margin-bottom: 0.1rem; /* Margem inferior mínima. */
        line-height: 1.2; /* Altura da linha para melhor legibilidade. */
    }}
    .pe-card-metric-value {{ /* Valor da métrica dentro do card (ex: número de participantes) */
        font-size: 1.15em; /* Tamanho da fonte, um pouco maior que o rótulo. */
        font-weight: bold; /* Texto em negrito. */
        color: {COLOR_SECONDARY}; /* Cor do texto (cor secundária da empresa). */
        margin-bottom: 0; /* Sem margem inferior. */
        line-height: 1.2; /* Altura da linha. */
    }}
    .pe-card-metric-value-alt {{ /* Estilo alternativo para valor de métrica no card (ex: número de esperados) */
        color: {COLOR_PRIMARY}; /* Usa a cor primária da empresa. */
    }}

    /* --- ESTILOS GERAIS PARA TÍTULOS (H1, H2, H4, H5) --- */
    h1, h2, h4, h5 {{
        color: {COLOR_PRIMARY}; /* Define a cor primária para estes níveis de título. */
    }}

    /* --- ESTILOS PARA O CABEÇALHO DO EXPANSOR (ST.EXPANDER) --- */
    div[data-testid="stExpander"] summary {{
        font-weight: bold; /* Texto do sumário do expansor em negrito. */
        color: {COLOR_PRIMARY}; /* Cor do texto do sumário. */
    }}

    /* --- ESTILOS PARA IMAGENS (ST.IMAGE) --- */
    div[data-testid="stImage"] img {{
        object-fit: contain !important; /* Garante que a imagem inteira seja visível, ajustando-se dentro do container. 'cover' preencheria o espaço, podendo cortar. */
        max-height: 50px; /* Altura máxima para as imagens (logos). Ajuste conforme o tamanho desejado para os logos. */
    }}
    h3 {{ /* Estilo específico para H3, usado para o título do mapa */
        color: {COLOR_PRIMARY}; /* Cor do texto. */
        font-size: 1.2em !important; /* Tamanho da fonte. '!important' para sobrescrever outros estilos se necessário. */
        margin-bottom: -0.1rem !important; /* Margem inferior negativa para aproximar do elemento abaixo. */
    }}
    div[data-testid="stImage"] {{ /* Container da imagem */
        display: flex; /* Usa flexbox para alinhamento. */
        align-items: center; /* Alinha a imagem verticalmente ao centro. */
        justify-content: center; /* Alinha a imagem horizontalmente ao centro. */
        min-height: 25px; /* Altura mínima para o container do logo. */
        padding-top: 30px; /* Espaçamento superior para afastar o logo do topo da coluna. Ajuste conforme o layout. */
        padding-bottom: 0.1px; /* Espaçamento inferior mínimo. */
    }}
    h2, h3 {{ /* Ajuste adicional para margens de H2 e H3 */
        margin-bottom: 0.1rem; /* Margem inferior pequena. */
    }}

    /* --- ESTILOS PARA LINHAS HORIZONTAIS (HR) --- */
    hr {{
        margin: 0.5rem 0 !important; /* Margens verticais e horizontais. Ajuste para mais ou menos espaço ao redor da linha. */
        height: 1px; /* Espessura da linha. */
        background-color: #e0e0e0; /* Cor da linha (cinza claro). */
        border: none; /* Remove a borda padrão. */
    }}
    .main .block-container hr {{ /* Linha horizontal dentro do container principal */
        margin: 0.3rem 0 !important; /* Margens verticais menores para um espaçamento mais compacto. */
    }}

    /* --- CONTROLE DE ALTURA E OVERFLOW PARA CONTAINERS DE MAPA (FOLIUM) --- */
    div[data-testid="element-container"]:has(> iframe),
    div[data-testid="element-container"]:has(> div.folium-map) {{
        height: {MAP_SECTION_HEIGHT_PX}px !important; /* Altura fixa para a seção do mapa, vinda da variável Python. Ajuste 'MAP_SECTION_HEIGHT_PX' no script se necessário. */
        overflow: hidden !important; /* Esconde qualquer conteúdo que transborde a altura definida, evitando barras de rolagem indesejadas no container. */
        margin-bottom: 0rem !important; /* Margem inferior negativa para compensar espaçamentos extras e juntar mais ao conteúdo abaixo. */
        padding-bottom: 0rem !important; /* Remove padding inferior do container. */
    }}

    /* Garante que o iframe ou o div do mapa preencha totalmente o container definido acima */
    div[data-testid="element-container"]:has(> iframe) > iframe,
    div[data-testid="element-container"]:has(> div.folium-map) > div.folium-map {{
        height: 100% !important; /* Ocupa 100% da altura do pai (definido por MAP_SECTION_HEIGHT_PX). */
        width: 100% !important; /* Ocupa 100% da largura do pai. */
    }}

    .folium-map {{ /* Estilo específico para o mapa Folium */
         margin-bottom: 0rem !important; /* Remove margem inferior do mapa em si. */
    }}

    /* --- ALINHAMENTO VERTICAL PARA SELECTBOX (FILTRO DE MUNICÍPIO) --- */
    div[data-testid="stSelectbox"] {{
        padding-top: 0em; /* Remove padding superior do container do selectbox, ajudando no alinhamento com o rótulo. */
    }}

    /* ----- Início: CSS para diminuir Select Box (Filtro de Município no Mapa) e mudar cor do rótulo ----- */
    /* Ajusta a altura e a fonte do campo visível do select box */
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:first-child {{
        padding-top: 0rem !important; /* Padding superior dentro do selectbox (campo onde o texto aparece). Reduzido para diminuir altura. */
        padding-bottom: 0rem !important; /* Padding inferior dentro do selectbox. */
        padding-left: 0.5rem !important; /* Padding esquerdo. Ajuste para mais ou menos espaço antes do texto. */
        font-size: 0.775rem !important; /* Tamanho da fonte do texto dentro do selectbox. Ex: 12.4px se a base for 16px. Ajuste para legibilidade. */
        min-height: auto !important; /* Permite que a altura seja menor que o padrão do Streamlit. */
        height: 35px !important; /* Altura desejada para o selectbox. Ajuste este valor para torná-lo maior ou menor. */
        line-height: 1.4 !important; /* Altura da linha. Ajuste para centralizar o texto verticalmente, especialmente se alterar a 'height' ou 'font-size'. */
        width: 180px; /* Largura fixa para o selectbox. Pode mudar para 'auto' ou um valor em '%' para responsividade, ou ajustar o valor em px. */
    }}

    /* Ajusta o tamanho da seta (dropdown indicator) no select box */
    div[data-testid="stSelectbox"] div[data-baseweb="select"] svg {{
        width: 16px !important; /* Largura do ícone da seta. Ajuste para aumentar/diminuir a seta. */
        height: 16px !important; /* Altura do ícone da seta. Ajuste para aumentar/diminuir a seta. */
    }}
    /* ----- Fim: CSS para diminuir Select Box ----- */

    /* --- INÍCIO: FIX PARA ESPAÇO EM BRANCO DO LOCALSTORAGE --- */
    /* Este seletor localiza o container que envolve o iframe específico
       do streamlit_local_storage (usando o atributo 'title' do iframe)
       e o oculta completamente, removendo o espaço em branco no final da página. */
    div[data-testid="element-container"]:has(iframe[title="streamlit_local_storage.st_local_storage"]) {{
        display: none !important;
    }}
    /* --- FIM: FIX PARA ESPAÇO EM BRANCO DO LOCALSTORAGE --- */

</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# Rodapé
#st.markdown("---") # Linha divisória antes do rodapé
#st.markdown(f"<p style='text-align:center; color:{COLOR_PRIMARY}; font-size:0.9em; margin-top: 0rem !important; margin-bottom: 0rem !important;'>{st.session_state.get('app_title', 'Painel de Simulado PAE')} | Desenvolvido para visualização otimizada de dados</p>", unsafe_allow_html=True)