from dataclasses import dataclass
from os import path, makedirs, listdir
import shutil
from django.db import IntegrityError, transaction
from core.models import Video, VideoMedia

@dataclass
class VideoService:
    """
    Serviço de Vídeo
    Esta classe fornece métodos para gerenciar o upload e processamento de vídeos.
    Atributos:
        storage (Storage): Instância de armazenamento para gerenciar chunks de vídeo.
    Métodos:
        get_chunk_directory(video_id: int) -> str:
            Retorna o diretório temporário para armazenar os chunks de vídeo.
        find_video(video_id: int) -> Video:
            Encontra e retorna um vídeo pelo seu ID.
        process_upload(video_id: int, chunk_index: int, chunk: bytes) -> None:
            Processa o upload de um chunk de vídeo. Atualiza o status do vídeo e armazena o chunk.
        __prepare_video_media(video: Video) -> VideoMedia:
            Prepara e retorna a instância de VideoMedia associada ao vídeo. Cria uma nova instância se não existir.
        finalize_upload(video_id: int, total_chunks: int) -> None:
            Finaliza o upload de um vídeo. Valida os chunks e atualiza o status do vídeo.
        __validate_chunks(video_path: str, total_chunks: int) -> bool:
            Valida se todos os chunks de vídeo existem no diretório especificado.
        upload_chunks_to_external_storage(video_id: int) -> None:
            Move os chunks de vídeo para um armazenamento externo.
        register_processed_video_path(video_id: int, video_path: str) -> None:
            Registra o caminho do vídeo processado e atualiza o status do vídeo.
    """

    storage: 'Storage'

    def get_chunk_directory(self, video_id: int) -> str:
        return f'/tmp/videos/{video_id}'

    def find_video(self, video_id: int) -> Video:
        return Video.objects.get(id=video_id)

    def process_upload(self, video_id: int, chunk_index: int, chunk: bytes) -> None:
        video = self.find_video(video_id)
        directory = self.get_chunk_directory(video_id)

        # Atualiza o status para 'UPLOADED_STARTED' e armazena o chunk
        with transaction.atomic():
            video_media = self.__prepare_video_media(video)

            if video_media.status == VideoMedia.Status.PROCESS_STARTED: #upload finalizado
                raise VideoMediaInvalidStatusException('An upload is already in progress.')

            # Se o status já está em 'UPLOADED_STARTED', continua armazenando os chunks
            if video_media.status == VideoMedia.Status.UPLOADED_STARTED:
                self.storage.storage_chunk(str(video_media.video_path), chunk_index, chunk)
                return

            # Se o processamento já terminou, reinicia o caminho do diretório de chunks
            if video_media.status == VideoMedia.Status.PROCESS_FINISHED:
                video_media.video_path = directory
                video.is_published = False
                video.save()

            video_media.status = VideoMedia.Status.UPLOADED_STARTED
            video_media.save()
            self.storage.storage_chunk(str(video_media.video_path), chunk_index, chunk)

    def __prepare_video_media(self, video: Video) -> VideoMedia:
        try:
            video_media = video.video_media
        except Video.video_media.RelatedObjectDoesNotExist:
            try:
                video_media = VideoMedia.objects.create(
                    video=video,
                    status=VideoMedia.Status.UPLOADED_STARTED,
                    video_path=self.get_chunk_directory(video.id)
                )
            except IntegrityError:
                video_media = VideoMedia.objects.get(video=video)
        return video_media

    def finalize_upload(self, video_id: int, total_chunks) -> None:
        video = self.find_video(video_id)
        
        try:
            video_media = video.video_media
            if video_media.status != VideoMedia.Status.UPLOADED_STARTED:
                raise VideoMediaInvalidStatusException('Upload must be started to finish it.')
            is_chunks_valid = self.__validate_chunks(str(video.video_media.video_path), total_chunks)
            if not is_chunks_valid:
                raise VideoChunkUploadException('Chunks are invalid.')
            
            video_media.status = VideoMedia.Status.PROCESS_STARTED
            video_media.save()

            # rabbitmq
            
        except Video.video_media.RelatedObjectDoesNotExist:
            raise VideoMediaNotExistsException('Upload not started.')
    
    def __validate_chunks(self, video_path: str, total_chunks: int) -> bool:
        if not path.exists(video_path):
            return False

        for i in range(total_chunks):
            chunk_path = path.join(video_path, f'{i}.chunk')
            if not path.exists(chunk_path):
                return False
        
        return True
    
    def upload_chunks_to_external_storage(self, video_id: int) -> None:
        self.find_video(video_id)
        source_path = self.get_chunk_directory(video_id)
        dest_path = f'/media/uploads/{video_id}'
        self.storage.move_chunks(source_path, dest_path)
        # rabbitmq


    def register_processed_video_path(self, video_id: int, video_path) -> None:
        video = self.find_video(video_id)
        video_media = video.video_media
        if video_media.status != VideoMedia.Status.PROCESS_STARTED:
            raise VideoMediaInvalidStatusException('Processing must be started to finish it.')
        video_media.video_path = video_path
        video_media.status = VideoMedia.Status.PROCESS_FINISHED
        video_media.save()

def create_video_service_factory() -> VideoService:
    return VideoService(Storage())


class VideoMediaInvalidStatusException(Exception):
    pass   

class VideoMediaNotExistsException(Exception):
    pass

class VideoChunkUploadException(Exception):
    pass

class Storage:

    def storage_chunk(self, directory: str, chunk_index: int, chunk: bytes) -> None:
        if not path.exists(directory):
            makedirs(directory)
        
        chunk_path = path.join(directory, f'{chunk_index}.chunk')
        
        with open(chunk_path, 'wb') as chunk_file:
            chunk_file.write(chunk)

    def move_chunks(self, source_path: str, dest_path: str) -> None:

        if not path.exists(dest_path):
            makedirs(dest_path, exist_ok=True)

        for filename in listdir(source_path):
            file_path = path.join(source_path, filename)

            if path.isfile(file_path):
                try:
                    shutil.move(file_path, path.join(dest_path, filename))
                    print(f"Arquivo {source_path}/{filename} movido para {dest_path}.")
                except Exception as e:
                    print(f"Erro ao mover o arquivo {source_path}/{filename}: {e}")
            else:
                print(f"{file_path} não é um arquivo.")
