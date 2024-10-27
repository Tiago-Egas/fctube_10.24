from django import forms

MAX_VIDEO_CHUNK_SIZE = 1 * 1024 * 1024  # 1 MB

class VideoChunkUploadForm(forms.Form):
    """
    Formulário para upload de chunks de vídeo.
    Atributos:
        chunk (forms.FileField): Campo obrigatório para o arquivo chunk.
        chunkIndex (forms.IntegerField): Campo obrigatório para o índice do chunk, deve ser um valor inteiro maior ou igual a 0.
    Métodos:
        clean_chunk(): Valida o campo 'chunk'. Verifica se o tamanho do chunk é menor ou igual ao tamanho máximo permitido (MAX_VIDEO_CHUNK_SIZE).
                       Se o tamanho for maior, lança uma ValidationError indicando que o arquivo deve ser um vídeo no formato MP4.
    """
    chunk = forms.FileField(required=True)  # O arquivo chunk
    chunkIndex = forms.IntegerField(min_value=0, required=True)  # Índice do chunk (deve ser >= 0)

    def clean_chunk(self):
        chunk = self.cleaned_data.get('chunk')
        
        if chunk.size > MAX_VIDEO_CHUNK_SIZE:
            raise forms.ValidationError('O arquivo deve ser um vídeo no formato MP4.')

        return chunk
    
class VideoChunkFinishUploadForm(forms.Form):
    fileName = forms.CharField(max_length=255, required=True)  # Nome do arquivo
    totalChunks = forms.IntegerField(min_value=1, required=True)  # Total de chunks (deve ser >= 1)